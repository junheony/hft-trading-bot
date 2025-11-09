"""
HFT Bot v0.7 - Main Bot Module
"""

import asyncio
import uuid
from datetime import datetime
from typing import Dict, Any, List

from core import (
    TradingConfig, Logger, Position, Trade, SignalType, ExitReason
)
from strategy import WeightedMultiStrategy
from risk import RiskManager
from ai_model import AIModel
from exchange import ExchangeAdapter
from position import PositionManager
from telegram_bot import TelegramBot


class HFTBot:
    """
    메인 HFT 봇
    - 심볼별 독립 데이터 피드
    - 원자적 진입/청산
    - 완전한 에러 핸들링
    """
    
    def __init__(
        self,
        config: TradingConfig,
        logger: Logger,
        exchange: ExchangeAdapter,
        strategy: WeightedMultiStrategy,
        position_manager: PositionManager,
        risk_manager: RiskManager,
        ai_model: Optional[AIModel] = None,
        telegram: Optional[TelegramBot] = None
    ):
        self.config = config
        self.logger = logger
        self.exchange = exchange
        self.strategy = strategy
        self.pm = position_manager
        self.risk = risk_manager
        self.ai = ai_model
        self.telegram = telegram
        
        self.running = False
        self.dashboard_state = {
            'status': 'STOPPED',
            'symbols': {},
            'positions': [],
            'daily_stats': {}
        }
        
        # 텔레그램 봇 컨트롤러 설정
        if self.telegram:
            self.telegram.set_bot_controller(self)
    
    async def symbol_feed_loop(self, symbol: str):
        """
        심볼별 독립 데이터 피드
        각 심볼마다 별도 태스크로 실행
        """
        self.logger.info(f"Feed started: {symbol}")
        
        while self.running:
            try:
                # 이미 포지션 있으면 스킵
                if self.pm.has_position_for_symbol(symbol):
                    await asyncio.sleep(0.1)
                    continue
                
                # 오더북 + 티커
                orderbook = await self.exchange.fetch_orderbook(symbol)
                ticker = await self.exchange.fetch_ticker(symbol)
                
                current_price = ticker['last']
                current_volume = ticker.get('quoteVolume', 0)
                
                # 신호 생성
                signal, signal_score, indicators = self.strategy.generate_signal(
                    orderbook,
                    current_price,
                    current_volume
                )
                
                # Dashboard 업데이트
                self.dashboard_state['symbols'][symbol] = {
                    'price': current_price,
                    'spread_bps': orderbook.spread_bps,
                    'signal_score': signal_score,
                    'indicators': indicators
                }
                
                # 진입 시도
                if signal == SignalType.LONG:
                    await self._try_entry(symbol, signal, signal_score, orderbook, indicators)
                
            except Exception as e:
                self.logger.error(f"Feed error [{symbol}]: {e}")
                await asyncio.sleep(1)
    
    async def _try_entry(
        self,
        symbol: str,
        signal: SignalType,
        signal_score: float,
        orderbook,
        indicators: Dict[str, float]
    ):
        """진입 시도 (원자적)"""
        try:
            # 리스크 체크
            can_enter, reason = self.risk.can_enter_position(
                self.pm.get_position_count(),
                self.config.trade_amount_krw
            )
            
            if not can_enter:
                self.logger.warning(f"{symbol} | {reason}")
                return
            
            # 유동성 체크
            if not orderbook.liquidity_check(self.config.trade_amount_krw):
                self.logger.warning(f"{symbol} | Insufficient liquidity")
                return
            
            # 스프레드 체크
            if orderbook.spread_bps > 10:
                self.logger.warning(f"{symbol} | Spread too wide: {orderbook.spread_bps:.2f}bps")
                return
            
            # AI 필터
            if self.config.use_ai_filter and self.ai:
                features = self.strategy.extract_features(symbol)
                if features is not None:
                    prediction, confidence = self.ai.predict(features)
                    
                    if prediction == 0 or confidence < self.config.ai_confidence_threshold:
                        self.logger.info(
                            f"{symbol} | AI Filter REJECTED | "
                            f"Prediction: {prediction} | Confidence: {confidence:.3f}"
                        )
                        return
                    
                    indicators['ai_confidence'] = confidence
            
            # 주문 실행 (재시도 포함)
            avg_price, filled_amount, fee = await self.exchange.create_market_buy_with_retry(
                symbol,
                self.config.trade_amount_krw,
                max_retries=self.config.entry_retry_max
            )
            
            # 포지션 생성
            position = Position(
                position_id=str(uuid.uuid4()),
                symbol=symbol,
                side=signal,
                entry_time=datetime.now(),
                entry_price=avg_price,
                amount=filled_amount,
                entry_fee=fee,
                signal_score=signal_score,
                indicators=indicators,
                highest_price=avg_price
            )
            
            # 포지션 오픈 (원자적)
            await self.pm.open_position(position)
            
            # 로깅
            self.logger.log_entry(position)
            
            # 텔레그램 알림
            if self.telegram:
                await self.telegram.notify_entry(position)
            
            # Dashboard
            self._update_dashboard_positions()
            
        except Exception as e:
            self.logger.error(f"Entry failed [{symbol}]: {e}")
    
    async def exit_loop(self):
        """청산 모니터링 루프"""
        self.logger.info("Exit loop started")
        
        while self.running:
            try:
                positions = self.pm.get_all_positions()
                
                if not positions:
                    await asyncio.sleep(0.1)
                    continue
                
                for position in positions:
                    try:
                        # 현재가
                        ticker = await self.exchange.fetch_ticker(position.symbol)
                        current_price = ticker['last']
                        
                        # 트레일링 스톱 업데이트
                        self.pm.update_trailing_stop(position.position_id, current_price)
                        
                        # 청산 조건 체크
                        exit_reason = self._check_exit_conditions(position, current_price)
                        
                        if exit_reason:
                            await self._execute_exit(position, exit_reason)
                    
                    except Exception as e:
                        self.logger.error(f"Exit check error [{position.symbol}]: {e}")
            
            except Exception as e:
                self.logger.error(f"Exit loop error: {e}")
                await asyncio.sleep(1)
    
    def _check_exit_conditions(
        self,
        position: Position,
        current_price: float
    ) -> Optional[ExitReason]:
        """청산 조건 체크"""
        if position.side == SignalType.LONG:
            pnl_rate = (current_price - position.entry_price) / position.entry_price
        else:
            pnl_rate = (position.entry_price - current_price) / position.entry_price
        
        # 익절
        if pnl_rate >= self.config.take_profit_rate:
            return ExitReason.TAKE_PROFIT
        
        # 손절
        if pnl_rate <= -self.config.stop_loss_rate:
            return ExitReason.STOP_LOSS
        
        # 트레일링 스톱
        if self.pm.check_trailing_stop(position.position_id, current_price):
            return ExitReason.TRAILING_STOP
        
        # 타임컷
        holding_time = (datetime.now() - position.entry_time).total_seconds()
        if holding_time > self.config.time_cut_seconds:
            return ExitReason.TIME_CUT
        
        return None
    
    async def _execute_exit(self, position: Position, exit_reason: ExitReason):
        """청산 실행 (재시도 포함)"""
        try:
            # 주문 실행
            avg_price, fee = await self.exchange.create_market_sell_with_retry(
                position.symbol,
                position.amount,
                max_retries=self.config.exit_retry_max
            )
            
            # 포지션 청산
            trade = await self.pm.close_position(
                position.position_id,
                avg_price,
                fee,
                exit_reason
            )
            
            # 리스크 매니저 업데이트
            self.risk.record_trade(trade)
            
            # 로깅
            self.logger.log_exit(trade)
            
            # 텔레그램 알림
            if self.telegram:
                await self.telegram.notify_exit(trade)
            
            # Dashboard
            self._update_dashboard_positions()
            self.dashboard_state['daily_stats'] = self.risk.get_daily_stats()
            
        except Exception as e:
            self.logger.error(f"Exit execution failed [{position.symbol}]: {e}")
            
            # 긴급 알림
            if self.telegram:
                await self.telegram.notify_emergency(
                    f"Failed to close position: {position.symbol}\n"
                    f"Manual intervention required!"
                )
    
    def _update_dashboard_positions(self):
        """Dashboard 포지션 업데이트"""
        positions = self.pm.get_all_positions()
        self.dashboard_state['positions'] = [
            {
                'position_id': p.position_id,
                'symbol': p.symbol,
                'side': p.side.value,
                'entry_price': p.entry_price,
                'entry_time': p.entry_time.isoformat(),
                'amount': p.amount,
                'signal_score': p.signal_score
            }
            for p in positions
        ]
    
    async def daily_report_loop(self):
        """일일 리포트 전송"""
        from datetime import timedelta
        
        while self.running:
            try:
                now = datetime.now()
                next_midnight = (now + timedelta(days=1)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                sleep_seconds = (next_midnight - now).total_seconds()
                
                # 자정까지 대기
                await asyncio.sleep(sleep_seconds)
                
                # 리포트 전송
                stats = self.risk.get_daily_stats()
                
                if self.telegram:
                    await self.telegram.notify_daily_report(stats)
                
                self.logger.info(f"Daily report: {stats}")
                
            except Exception as e:
                self.logger.error(f"Daily report error: {e}")
                await asyncio.sleep(3600)
    
    async def run(self):
        """봇 실행"""
        self.running = True
        self.dashboard_state['status'] = 'RUNNING'
        
        self.logger.info("="*60)
        self.logger.info("HFT Bot v0.7 Started")
        self.logger.info(f"Exchange: {self.config.exchange_type.value}")
        self.logger.info(f"Symbols: {', '.join(self.config.symbols)}")
        self.logger.info(f"Trade Amount: {self.config.trade_amount_krw:,.0f} KRW")
        self.logger.info(f"AI Filter: {self.config.use_ai_filter}")
        self.logger.info("="*60)
        
        try:
            # 모든 태스크 시작
            tasks = [
                # 심볼별 피드
                *[asyncio.create_task(self.symbol_feed_loop(symbol)) for symbol in self.config.symbols],
                # 청산 루프
                asyncio.create_task(self.exit_loop()),
                # 일일 리포트
                asyncio.create_task(self.daily_report_loop())
            ]
            
            await asyncio.gather(*tasks)
            
        except Exception as e:
            self.logger.error(f"Bot crashed: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.running = False
            self.dashboard_state['status'] = 'STOPPED'
            self.logger.info("Bot stopped")
    
    async def stop(self):
        """봇 중지"""
        self.running = False
    
    async def emergency_stop(self, reason: str):
        """긴급 중지"""
        self.logger.error(f"Emergency stop: {reason}")
        self.risk.activate_emergency_stop(reason)
        
        # 모든 포지션 강제 청산
        positions = self.pm.get_all_positions()
        for pos in positions:
            try:
                await self._execute_exit(pos, ExitReason.EMERGENCY)
            except:
                pass
        
        self.running = False
    
    def resume(self):
        """재개 (긴급 중지 해제)"""
        self.risk.deactivate_emergency_stop()
    
    # === 텔레그램 명령어용 메서드 ===
    
    def get_status(self) -> Dict[str, Any]:
        """상태 조회"""
        stats = self.risk.get_daily_stats()
        return {
            'status': 'RUNNING' if self.running else 'STOPPED',
            'positions_count': self.pm.get_position_count(),
            'daily_pnl': stats['pnl'],
            'win_rate': stats['win_rate']
        }
    
    def get_positions(self) -> List[Position]:
        """포지션 목록"""
        return self.pm.get_all_positions()