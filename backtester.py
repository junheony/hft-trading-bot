"""
HFT Bot v0.7 - Backtester Module
완전한 백테스팅 엔진
"""

import glob
import json
import numpy as np
from typing import Dict, Any, List, Optional
from datetime import datetime

from core import (
    TradingConfig, OrderBook, SignalType, ExitReason, Logger
)
from strategy import WeightedMultiStrategy


class Backtester:
    """
    백테스트 엔진
    - Train/Test Split
    - 정확한 슬리피지/수수료 반영
    - Sharpe, MDD, Profit Factor 계산
    """
    
    def __init__(self, config: TradingConfig, logger: Logger):
        self.config = config
        self.logger = logger
    
    def load_data(self, symbol: str) -> List[Dict]:
        """데이터 로드"""
        pattern = os.path.join(
            self.config.backtest_data_dir,
            f"{symbol.replace('/', '_')}_*.jsonl"
        )
        files = glob.glob(pattern)
        
        if not files:
            raise FileNotFoundError(f"No data for {symbol}")
        
        data = []
        with open(files[0], 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    item = json.loads(line)
                    if item.get('type') == 'orderbook':
                        data.append(item['data'])
                except:
                    continue
        
        return data
    
    def run(self, symbol: str, use_test_data: bool = True) -> Dict[str, Any]:
        """
        백테스트 실행
        
        Args:
            symbol: 심볼
            use_test_data: True면 Test 데이터만 사용
        """
        self.logger.info("="*60)
        self.logger.info(f"Backtesting {symbol}")
        self.logger.info("="*60)
        
        # 데이터 로드
        all_data = self.load_data(symbol)
        self.logger.info(f"Loaded {len(all_data)} ticks")
        
        # Train/Test Split
        split_idx = int(len(all_data) * self.config.backtest_train_ratio)
        
        if use_test_data:
            data = all_data[split_idx:]
            self.logger.info(f"Using Test data: {len(data)} ticks")
        else:
            data = all_data
            self.logger.info(f"Using All data: {len(data)} ticks")
        
        # 전략 초기화
        strategy = WeightedMultiStrategy(self.config)
        
        # 시뮬레이션 변수
        trades = []
        position = None
        
        for i, ob_data in enumerate(data):
            ob = OrderBook(
                timestamp=datetime.now(),
                symbol=symbol,
                bids=ob_data['bids'][:self.config.orderbook_depth],
                asks=ob_data['asks'][:self.config.orderbook_depth]
            )
            
            current_price = ob_data['price']
            current_volume = ob_data.get('volume', 0)
            
            # 신호 생성
            signal, signal_score, indicators = strategy.generate_signal(
                ob, current_price, current_volume
            )
            
            # === 진입 ===
            if position is None and signal == SignalType.LONG:
                # 슬리피지 반영: Ask 1호가 기준
                ask_price = ob.asks[0][0]
                slippage = ask_price * (self.config.slippage_bps / 10000)
                entry_price = ask_price + slippage
                
                # 수수료
                entry_cost = self.config.trade_amount_krw
                entry_fee = entry_cost * self.config.taker_fee
                
                # 수량
                amount = entry_cost / entry_price
                
                position = {
                    'entry_idx': i,
                    'entry_price': entry_price,
                    'amount': amount,
                    'entry_fee': entry_fee,
                    'entry_time': i * 0.1,  # 틱당 0.1초 가정
                    'signal_score': signal_score,
                    'indicators': indicators,
                    'highest_price': entry_price
                }
            
            # === 청산 ===
            elif position is not None:
                # Bid 1호가 기준
                bid_price = ob.bids[0][0]
                slippage = bid_price * (self.config.slippage_bps / 10000)
                exit_price = bid_price - slippage
                
                # 청산 조건 체크
                pnl_rate = (exit_price - position['entry_price']) / position['entry_price']
                holding_ticks = i - position['entry_idx']
                holding_seconds = holding_ticks * 0.1
                
                # Trailing Stop 업데이트
                if self.config.trailing_stop:
                    if current_price > position['highest_price']:
                        position['highest_price'] = current_price
                
                exit_reason = None
                
                # 익절
                if pnl_rate >= self.config.take_profit_rate:
                    exit_reason = ExitReason.TAKE_PROFIT
                
                # 손절
                elif pnl_rate <= -self.config.stop_loss_rate:
                    exit_reason = ExitReason.STOP_LOSS
                
                # 트레일링 스톱
                elif self.config.trailing_stop:
                    drop_from_high = (position['highest_price'] - current_price) / position['highest_price']
                    if drop_from_high >= self.config.trailing_stop_pct:
                        exit_reason = ExitReason.TRAILING_STOP
                
                # 타임컷
                elif holding_seconds > self.config.time_cut_seconds:
                    exit_reason = ExitReason.TIME_CUT
                
                # 청산 실행
                if exit_reason:
                    exit_cost = exit_price * position['amount']
                    exit_fee = exit_cost * self.config.taker_fee
                    
                    gross_pnl = (exit_price - position['entry_price']) * position['amount']
                    net_pnl = gross_pnl - position['entry_fee'] - exit_fee
                    
                    trades.append({
                        'entry_idx': position['entry_idx'],
                        'exit_idx': i,
                        'entry_price': position['entry_price'],
                        'exit_price': exit_price,
                        'amount': position['amount'],
                        'gross_pnl': gross_pnl,
                        'net_pnl': net_pnl,
                        'entry_fee': position['entry_fee'],
                        'exit_fee': exit_fee,
                        'exit_reason': exit_reason.value,
                        'holding_ticks': holding_ticks,
                        'holding_seconds': holding_seconds,
                        'signal_score': position['signal_score'],
                        'indicators': position['indicators']
                    })
                    
                    position = None
        
        # 통계 계산
        return self._calculate_statistics(trades)
    
    def _calculate_statistics(self, trades: List[Dict]) -> Dict[str, Any]:
        """통계 계산"""
        if not trades:
            self.logger.warning("No trades executed")
            return {'error': 'No trades'}
        
        pnls = [t['net_pnl'] for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        
        # 기본 통계
        total_pnl = sum(pnls)
        total_trades = len(trades)
        win_rate = len(wins) / total_trades
        
        avg_win = np.mean(wins) if wins else 0
        avg_loss = np.mean(losses) if losses else 0
        
        # Sharpe Ratio
        mean_return = np.mean(pnls)
        std_return = np.std(pnls)
        sharpe = (mean_return / std_return * np.sqrt(252)) if std_return > 0 else 0
        
        # Max Drawdown
        cumulative = np.cumsum(pnls)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = cumulative - running_max
        max_drawdown = np.min(drawdown)
        max_drawdown_pct = (max_drawdown / np.max(running_max) * 100) if np.max(running_max) > 0 else 0
        
        # Profit Factor
        total_wins = sum(wins) if wins else 0
        total_losses = abs(sum(losses)) if losses else 1
        profit_factor = total_wins / total_losses if total_losses > 0 else 0
        
        # Exit Reason 분포
        exit_reasons = {}
        for t in trades:
            reason = t['exit_reason']
            exit_reasons[reason] = exit_reasons.get(reason, 0) + 1
        
        # 평균 보유 시간
        avg_holding = np.mean([t['holding_seconds'] for t in trades])
        
        # 결과
        stats = {
            'total_trades': total_trades,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_drawdown,
            'max_drawdown_pct': max_drawdown_pct,
            'profit_factor': profit_factor,
            'avg_holding_seconds': avg_holding,
            'exit_reasons': exit_reasons,
            'trades': trades
        }
        
        # 로그 출력
        self.logger.info("="*60)
        self.logger.info("BACKTEST RESULTS")
        self.logger.info("="*60)
        self.logger.info(f"Total Trades      : {total_trades}")
        self.logger.info(f"Win Rate          : {win_rate*100:.1f}%")
        self.logger.info(f"Total PnL         : {total_pnl:,.0f} KRW")
        self.logger.info(f"Avg Win           : {avg_win:,.0f} KRW")
        self.logger.info(f"Avg Loss          : {avg_loss:,.0f} KRW")
        self.logger.info(f"Sharpe Ratio      : {sharpe:.3f}")
        self.logger.info(f"Max Drawdown      : {max_drawdown:,.0f} KRW ({max_drawdown_pct:.1f}%)")
        self.logger.info(f"Profit Factor     : {profit_factor:.2f}")
        self.logger.info(f"Avg Holding Time  : {avg_holding:.1f}s")
        self.logger.info(f"Exit Reasons      : {exit_reasons}")
        self.logger.info("="*60)
        
        return stats