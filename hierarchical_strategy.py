"""
HFT Bot v0.9 - Hierarchical Strategy
3단계 계층적 의사결정: Macro → Strategic → Tactical
"""

from typing import Optional, Tuple, Dict, Any
import numpy as np

from core import TradingConfig, OrderBook, Logger
from signal import Signal, SignalDirection, SignalLevel, ExecutionSignal
from agents import MacroFilterAgent, StrategyAgent, ExecutionAgent
from risk import RiskManager
from indicators import TechnicalIndicators


class HierarchicalStrategy:
    """
    계층적 전략 시스템 (v0.9)

    Level 1 (Macro Filter): 거시적 시장 상태 필터링
        ↓
    Level 2 (Strategic): 기술적 지표 기반 방향성 결정
        ↓
    Level 3 (Tactical): 오더북 미시구조 기반 실행 타이밍

    기존 WeightedMultiStrategy를 대체하는 개선된 아키텍처
    """

    def __init__(self, config: TradingConfig, risk_manager: RiskManager, logger: Logger):
        self.config = config
        self.risk_manager = risk_manager
        self.logger = logger

        # 3단계 에이전트 초기화
        self.macro_agent = MacroFilterAgent(config, risk_manager, logger)
        self.strategy_agent = StrategyAgent(config, logger)
        self.execution_agent = ExecutionAgent(config, risk_manager, logger)

        # 최근 신호 캐시 (TTL 체크용)
        self.last_macro_signal: Optional[Signal] = None
        self.last_strategic_signal: Optional[Signal] = None

    def generate_signal(
        self,
        orderbook: OrderBook,
        current_price: float,
        current_volume: float
    ) -> Tuple[Optional[ExecutionSignal], Dict[str, Any]]:
        """
        계층적 신호 생성

        Returns:
            (execution_signal, metadata)
        """
        metadata = {
            'symbol': orderbook.symbol,
            'price': current_price,
            'timestamp': orderbook.timestamp
        }

        # === Level 1: Macro Filter ===
        # 캐시된 신호가 있고 유효하면 재사용 (성능 최적화)
        if self.last_macro_signal and self.last_macro_signal.is_valid():
            macro_signal = self.last_macro_signal
            metadata['macro_cached'] = True
        else:
            macro_signal = self.macro_agent.analyze()
            self.last_macro_signal = macro_signal
            metadata['macro_cached'] = False

        metadata['macro_signal'] = {
            'direction': macro_signal.direction.value,
            'score': macro_signal.score,
            'reason': macro_signal.reason,
            'ttl_remaining': macro_signal.remaining_ttl()
        }

        # Macro 필터 통과 실패 → 진입 불가
        if macro_signal.direction == SignalDirection.NEUTRAL and macro_signal.score == 0.0:
            self.logger.debug(f"[L1 Macro] BLOCKED: {macro_signal.reason}")
            return None, metadata

        # === Level 2: Strategic Signal ===
        # Strategic 신호도 캐싱 (30초 TTL)
        if self.last_strategic_signal and self.last_strategic_signal.is_valid():
            strategic_signal = self.last_strategic_signal
            metadata['strategic_cached'] = True
        else:
            strategic_signal = self.strategy_agent.analyze(
                orderbook.symbol,
                current_price,
                current_volume
            )
            self.last_strategic_signal = strategic_signal
            metadata['strategic_cached'] = False

        metadata['strategic_signal'] = {
            'direction': strategic_signal.direction.value,
            'score': strategic_signal.score,
            'reason': strategic_signal.reason,
            'ttl_remaining': strategic_signal.remaining_ttl(),
            'indicators': strategic_signal.metadata if strategic_signal.metadata else {}
        }

        # Strategic 신호가 NEUTRAL → 명확한 방향성 없음
        if strategic_signal.direction == SignalDirection.NEUTRAL:
            self.logger.debug(f"[L2 Strategic] NEUTRAL: {strategic_signal.reason}")
            return None, metadata

        # Strategic 신호가 임계값 미달
        if strategic_signal.score < self.config.signal_threshold:
            self.logger.debug(
                f"[L2 Strategic] LOW CONFIDENCE: "
                f"score={strategic_signal.score:.3f} < {self.config.signal_threshold}"
            )
            return None, metadata

        # === Level 3: Tactical Execution ===
        # 변동성 계산 (포지션 사이징용)
        volatility = self._calculate_volatility(orderbook.symbol)

        execution_signal = self.execution_agent.analyze(
            orderbook=orderbook,
            strategic_signal=strategic_signal,
            current_price=current_price,
            volatility=volatility
        )

        metadata['execution_signal'] = {
            'direction': execution_signal.direction.value,
            'score': execution_signal.score,
            'reason': execution_signal.reason,
            'position_size_krw': execution_signal.position_size_krw,
            'expected_slippage': execution_signal.expected_slippage,
            'ttl_remaining': execution_signal.remaining_ttl()
        }
        metadata['volatility'] = volatility

        # Execution 신호가 NEUTRAL → 실행 타이밍 불량
        if execution_signal.direction == SignalDirection.NEUTRAL:
            self.logger.debug(f"[L3 Execution] UNFAVORABLE: {execution_signal.reason}")
            return None, metadata

        # === 최종 신호 생성 성공 ===
        self.logger.info(
            f"[✓ HIERARCHICAL SIGNAL] {execution_signal.direction.value} | "
            f"Macro={macro_signal.score:.2f} → "
            f"Strategic={strategic_signal.score:.2f} → "
            f"Execution={execution_signal.score:.2f} | "
            f"Size={execution_signal.position_size_krw:,.0f} KRW"
        )

        return execution_signal, metadata

    def _calculate_volatility(self, symbol: str) -> float:
        """최근 가격 변동성 계산"""
        buffer = self.strategy_agent.get_buffer(symbol)

        if not buffer.is_ready(20):
            return 0.02  # 기본값 2%

        prices = buffer.get_prices()
        returns = np.diff(prices) / prices[:-1]
        volatility = np.std(returns)

        return volatility

    def extract_features(self, symbol: str) -> Optional[np.ndarray]:
        """
        AI 모델용 피처 추출
        계층적 신호들을 피처로 포함
        """
        buffer = self.strategy_agent.get_buffer(symbol)

        if not buffer.is_ready(50):
            return None

        prices = buffer.get_prices()

        # 기존 기술적 지표
        rsi = TechnicalIndicators.calculate_rsi(prices, self.config.rsi_period)
        macd_result = TechnicalIndicators.calculate_macd(
            prices, self.config.macd_fast, self.config.macd_slow, self.config.macd_signal
        )
        bb_result = TechnicalIndicators.calculate_bollinger_bands(
            prices, self.config.bb_period, self.config.bb_std_dev
        )

        if not all([rsi, macd_result, bb_result]):
            return None

        macd_line, signal_line, histogram = macd_result
        _, _, _, bb_position = bb_result

        # W-OBI (최근)
        wobi_ratios = buffer.get_wobi_ratios()
        if len(wobi_ratios) < 10:
            return None

        recent_wobi = wobi_ratios[-1] if wobi_ratios else 0.0

        # 변동성
        volatility = self._calculate_volatility(symbol)

        # Macro 신호 강도
        macro_score = self.last_macro_signal.score if self.last_macro_signal else 0.5

        # Strategic 신호 강도
        strategic_score = self.last_strategic_signal.score if self.last_strategic_signal else 0.5

        # 피처 벡터 (11차원)
        features = np.array([
            rsi / 100.0,  # 0~1 정규화
            (macd_line - signal_line) / (abs(macd_line) + 1e-6),  # MACD 모멘텀
            histogram / (abs(histogram) + 1e-6),
            bb_position,
            recent_wobi,
            volatility * 100,  # 0~1 스케일
            macro_score,
            strategic_score,
            len(self.risk_manager.active_positions) / max(self.config.max_positions, 1),
            self.risk_manager.consecutive_losses / max(self.config.max_consecutive_losses, 1),
            np.clip(self.risk_manager.daily_pnl / 100000, -1, 1)  # 정규화
        ])

        return features
