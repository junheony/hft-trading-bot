"""
HFT Bot v0.9 - Hierarchical Agent Architecture
계층적 에이전트 시스템: Macro → Strategic → Tactical
"""

from datetime import datetime
from typing import Optional, Dict, Any
import numpy as np

from core import TradingConfig, OrderBook, Logger
from signal import Signal, SignalDirection, SignalLevel, ExecutionSignal
from indicators import TechnicalIndicators, IndicatorBuffer
from risk import RiskManager


class MacroFilterAgent:
    """
    Level 1: Macro Filter Agent
    역할: 거시적 시장 상태를 판단하여 진입 허용 여부 결정
    - 리스크 관리 상태 (일일 손실, 연속 손실, 긴급 정지)
    - 시장 변동성 체크
    - Sharpe Ratio 추세
    """

    def __init__(self, config: TradingConfig, risk_manager: RiskManager, logger: Logger):
        self.config = config
        self.risk_manager = risk_manager
        self.logger = logger

    def analyze(self) -> Signal:
        """거시적 필터 분석"""
        # 1. 긴급 정지 체크
        if self.risk_manager.emergency_stop:
            return Signal.no_signal(
                level=SignalLevel.MACRO,
                source="MacroFilterAgent",
                reason=f"Emergency stop activated: {self.risk_manager.emergency_reason}"
            )

        # 2. 일일 손실 한도 체크
        if self.risk_manager.daily_pnl <= self.config.max_daily_loss:
            return Signal.no_signal(
                level=SignalLevel.MACRO,
                source="MacroFilterAgent",
                reason=f"Daily loss limit reached: {self.risk_manager.daily_pnl:.0f} KRW"
            )

        # 3. 연속 손실 체크
        if self.risk_manager.consecutive_losses >= self.config.max_consecutive_losses:
            return Signal.no_signal(
                level=SignalLevel.MACRO,
                source="MacroFilterAgent",
                reason=f"Too many consecutive losses: {self.risk_manager.consecutive_losses}"
            )

        # 4. 최대 포지션 수 체크
        active_positions = len(self.risk_manager.active_positions)
        if active_positions >= self.config.max_positions:
            return Signal.no_signal(
                level=SignalLevel.MACRO,
                source="MacroFilterAgent",
                reason=f"Max positions reached: {active_positions}/{self.config.max_positions}"
            )

        # 5. Sharpe Ratio 체크 (최소 거래 이후)
        sharpe = self.risk_manager.calculate_sharpe_ratio()
        if len(self.risk_manager.trades_history) >= 10 and sharpe < -0.5:
            return Signal.no_signal(
                level=SignalLevel.MACRO,
                source="MacroFilterAgent",
                reason=f"Poor Sharpe Ratio: {sharpe:.3f} (negative performance)"
            )

        # 모든 체크 통과 → 진입 허용
        confidence = 0.8  # 기본 허용 신뢰도

        # Sharpe가 좋으면 confidence 증가
        if sharpe > 1.0:
            confidence = min(1.0, 0.8 + (sharpe - 1.0) * 0.1)

        return Signal(
            direction=SignalDirection.NEUTRAL,  # 방향성은 다음 단계에서 결정
            score=confidence,
            level=SignalLevel.MACRO,
            timestamp=datetime.now(),
            ttl_seconds=60,  # 1분간 유효
            source="MacroFilterAgent",
            reason="Market conditions acceptable",
            metadata={
                'daily_pnl': self.risk_manager.daily_pnl,
                'consecutive_losses': self.risk_manager.consecutive_losses,
                'sharpe_ratio': sharpe,
                'active_positions': active_positions
            }
        )


class StrategyAgent:
    """
    Level 2: Strategy Agent
    역할: 중기 기술적 지표를 분석하여 매매 방향성 결정
    - RSI, MACD, Bollinger Bands 통합
    - 가중치 기반 점수 계산
    - TTL: 30초 (HFT이므로 짧게)
    """

    def __init__(self, config: TradingConfig, logger: Logger):
        self.config = config
        self.logger = logger
        self.buffers: Dict[str, IndicatorBuffer] = {}

    def get_buffer(self, symbol: str) -> IndicatorBuffer:
        """심볼별 데이터 버퍼"""
        if symbol not in self.buffers:
            self.buffers[symbol] = IndicatorBuffer(max_size=200)
        return self.buffers[symbol]

    def analyze(self, symbol: str, price: float, volume: float) -> Signal:
        """전략적 분석"""
        buffer = self.get_buffer(symbol)
        buffer.add_data(price, volume)

        if not buffer.is_ready(50):
            return Signal.no_signal(
                level=SignalLevel.STRATEGIC,
                source="StrategyAgent",
                reason="Insufficient data for indicators"
            )

        prices = buffer.get_prices()

        # 1. RSI
        rsi = TechnicalIndicators.calculate_rsi(prices, self.config.rsi_period)
        rsi_score = 0.0
        if rsi is not None:
            if rsi < self.config.rsi_oversold:
                rsi_score = (self.config.rsi_oversold - rsi) / self.config.rsi_oversold
            elif rsi > self.config.rsi_overbought:
                rsi_score = -(rsi - self.config.rsi_overbought) / (100 - self.config.rsi_overbought)

        # 2. MACD
        macd_result = TechnicalIndicators.calculate_macd(
            prices, self.config.macd_fast, self.config.macd_slow, self.config.macd_signal
        )
        macd_score = 0.0
        if macd_result:
            macd_line, signal_line, histogram = macd_result
            if histogram > 0:
                macd_score = min(1.0, histogram / abs(macd_line) if macd_line != 0 else 0.5)
            else:
                macd_score = max(-1.0, histogram / abs(macd_line) if macd_line != 0 else -0.5)

        # 3. Bollinger Bands
        bb_result = TechnicalIndicators.calculate_bollinger_bands(
            prices, self.config.bb_period, self.config.bb_std_dev
        )
        bb_score = 0.0
        if bb_result:
            upper, middle, lower, bb_position = bb_result
            bb_score = -bb_position  # 하단이면 매수 신호

        # 가중 평균 (RSI 40%, MACD 40%, BB 20%)
        total_score = (
            rsi_score * 0.4 +
            macd_score * 0.4 +
            bb_score * 0.2
        )

        # 정규화: -1 ~ 1 → 0 ~ 1
        normalized_score = (total_score + 1.0) / 2.0

        # 방향성 결정
        if total_score > 0.3:
            direction = SignalDirection.LONG
        elif total_score < -0.3:
            direction = SignalDirection.SHORT
        else:
            direction = SignalDirection.NEUTRAL

        return Signal(
            direction=direction,
            score=normalized_score,
            level=SignalLevel.STRATEGIC,
            timestamp=datetime.now(),
            ttl_seconds=30,  # 30초간 유효
            source="StrategyAgent",
            reason=f"RSI={rsi:.1f}, MACD_hist={histogram if macd_result else 0:.2f}, BB_pos={bb_position if bb_result else 0:.2f}",
            metadata={
                'rsi': rsi,
                'rsi_score': rsi_score,
                'macd_histogram': histogram if macd_result else None,
                'macd_score': macd_score,
                'bb_position': bb_position if bb_result else None,
                'bb_score': bb_score,
                'total_score': total_score
            }
        )


class ExecutionAgent:
    """
    Level 3: Execution Agent
    역할: 오더북 미시구조를 분석하여 최적 실행 타이밍 결정
    - W-OBI (Weighted Order Book Imbalance) 전문화
    - 스프레드 체크
    - 깊이(Depth) 체크
    - TTL: 10초 (매우 짧음 - 오더북은 빠르게 변함)
    """

    def __init__(self, config: TradingConfig, risk_manager: RiskManager, logger: Logger):
        self.config = config
        self.risk_manager = risk_manager
        self.logger = logger
        self.buffers: Dict[str, IndicatorBuffer] = {}

    def get_buffer(self, symbol: str) -> IndicatorBuffer:
        """심볼별 WOBI 버퍼"""
        if symbol not in self.buffers:
            self.buffers[symbol] = IndicatorBuffer(max_size=self.config.wobi_window_size)
        return self.buffers[symbol]

    def analyze(
        self,
        orderbook: OrderBook,
        strategic_signal: Signal,
        current_price: float,
        volatility: float
    ) -> ExecutionSignal:
        """전술적 실행 분석"""

        # Strategic 신호가 LONG/SHORT가 아니면 실행 불가
        if strategic_signal.direction == SignalDirection.NEUTRAL:
            return ExecutionSignal.create(
                direction=SignalDirection.NEUTRAL,
                score=0.0,
                position_size_krw=0.0,
                source="ExecutionAgent",
                reason="No strategic direction"
            )

        # 1. W-OBI 계산
        wobi_ratio = self._calculate_wobi(orderbook)
        buffer = self.get_buffer(orderbook.symbol)
        buffer.add_data(current_price, wobi_ratio=wobi_ratio)

        if not buffer.is_ready(self.config.wobi_window_size):
            return ExecutionSignal.create(
                direction=SignalDirection.NEUTRAL,
                score=0.0,
                position_size_krw=0.0,
                source="ExecutionAgent",
                reason="Insufficient WOBI history"
            )

        wobi_ratios = buffer.get_wobi_ratios()
        mean_wobi = np.mean(wobi_ratios)
        std_wobi = np.std(wobi_ratios)

        if std_wobi == 0:
            z_score = 0.0
        else:
            z_score = (wobi_ratio - mean_wobi) / std_wobi

        # 2. 스프레드 체크
        spread = (orderbook.asks[0][0] - orderbook.bids[0][0]) / orderbook.bids[0][0]
        spread_ok = spread < 0.001  # 0.1% 이하

        # 3. 깊이 체크 (충분한 유동성)
        total_bid_qty = sum(qty for _, qty in orderbook.bids[:5])
        total_ask_qty = sum(qty for _, qty in orderbook.asks[:5])
        depth_ratio = total_bid_qty / total_ask_qty if total_ask_qty > 0 else 1.0

        # 4. 실행 조건 체크
        if strategic_signal.direction == SignalDirection.LONG:
            # 매수: WOBI가 양수(매수 압력) + 좁은 스프레드 + 충분한 Ask 깊이
            wobi_favorable = z_score > self.config.zscore_base_threshold
            depth_favorable = depth_ratio < 1.5  # Ask가 충분함
        else:  # SHORT
            # 매도: WOBI가 음수(매도 압력) + 좁은 스프레드 + 충분한 Bid 깊이
            wobi_favorable = z_score < -self.config.zscore_base_threshold
            depth_favorable = depth_ratio > 0.67  # Bid가 충분함

        immediate_entry = wobi_favorable and spread_ok and depth_favorable

        if not immediate_entry:
            return ExecutionSignal.create(
                direction=SignalDirection.NEUTRAL,
                score=0.0,
                position_size_krw=0.0,
                source="ExecutionAgent",
                reason=f"Unfavorable execution: z={z_score:.2f}, spread={spread:.4f}, depth={depth_ratio:.2f}"
            )

        # 5. 포지션 사이징 (동적 조절)
        position_size = self.risk_manager.calculate_position_size(
            volatility=volatility,
            confidence=strategic_signal.score
        )

        # 6. 예상 슬리피지
        expected_slippage = spread / 2  # 스프레드의 절반을 예상 슬리피지로

        # 실행 스코어 (WOBI 강도 + 전략 신뢰도)
        wobi_strength = min(1.0, abs(z_score) / 5.0)  # z-score 5 이상이면 1.0
        execution_score = (wobi_strength * 0.6 + strategic_signal.score * 0.4)

        return ExecutionSignal.create(
            direction=strategic_signal.direction,
            score=execution_score,
            position_size_krw=position_size,
            source="ExecutionAgent",
            reason=f"Favorable execution: WOBI_z={z_score:.2f}, spread={spread:.4f}",
            ttl_seconds=10,  # 10초만 유효
            expected_slippage=expected_slippage
        )

    def _calculate_wobi(self, orderbook: OrderBook) -> float:
        """W-OBI 계산 (가중 오더북 불균형)"""
        total_bid_value = sum(price * qty for price, qty in orderbook.bids[:10])
        total_ask_value = sum(price * qty for price, qty in orderbook.asks[:10])

        if total_bid_value + total_ask_value == 0:
            return 0.0

        wobi = (total_bid_value - total_ask_value) / (total_bid_value + total_ask_value)
        return wobi
