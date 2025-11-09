"""
HFT Bot v0.7 - Strategy Module
가중치 기반 멀티 전략 엔진
"""

import numpy as np
from typing import Tuple, Dict, Optional
from collections import deque

from core import TradingConfig, OrderBook, SignalType
from indicators import TechnicalIndicators, IndicatorBuffer


class WeightedMultiStrategy:
    """
    가중치 기반 멀티 전략
    
    각 지표의 신호를 0~1로 정규화하고 가중치를 곱한 뒤 합산
    총점이 signal_threshold 이상이면 진입
    """
    
    def __init__(self, config: TradingConfig):
        self.config = config
        
        # 심볼별 버퍼
        self.buffers: Dict[str, IndicatorBuffer] = {}
        
        # 동적 임계값 (심볼별)
        self.dynamic_thresholds: Dict[str, float] = {}
    
    def _get_buffer(self, symbol: str) -> IndicatorBuffer:
        """버퍼 가져오기"""
        if symbol not in self.buffers:
            self.buffers[symbol] = IndicatorBuffer(max_size=200)
            self.dynamic_thresholds[symbol] = self.config.zscore_base_threshold
        return self.buffers[symbol]
    
    def calculate_wobi_zscore(self, orderbook: OrderBook) -> Optional[float]:
        """W-OBI Z-Score 계산"""
        symbol = orderbook.symbol
        buffer = self._get_buffer(symbol)
        
        # W-OBI 비율 계산
        bids = orderbook.bids[:self.config.orderbook_depth]
        asks = orderbook.asks[:self.config.orderbook_depth]
        
        weights = np.arange(self.config.orderbook_depth, 0, -1)
        
        weighted_bid = sum(p * a * w for (p, a), w in zip(bids, weights))
        weighted_ask = sum(p * a * w for (p, a), w in zip(asks, weights))
        
        total = weighted_bid + weighted_ask
        if total == 0:
            return None
        
        wobi_ratio = weighted_bid / total
        buffer.wobi_ratios.append(wobi_ratio)
        
        if len(buffer.wobi_ratios) < self.config.wobi_window_size:
            return None
        
        ratios = buffer.get_wobi_ratios()[-self.config.wobi_window_size:]
        mean = np.mean(ratios)
        std = np.std(ratios)
        
        if std == 0:
            return None
        
        z_score = (wobi_ratio - mean) / std
        
        return z_score
    
    def update_dynamic_threshold(self, symbol: str):
        """
        연속 함수 기반 동적 임계값 조정
        z_threshold = base * (1 + k * volatility)
        """
        if not self.config.enable_dynamic_params:
            return
        
        buffer = self._get_buffer(symbol)
        
        if not buffer.is_ready(self.config.volatility_window):
            return
        
        prices = buffer.get_prices()[-self.config.volatility_window:]
        returns = np.diff(prices) / prices[:-1]
        volatility = np.std(returns)
        
        # 연속 함수: threshold = base * (1 + k * vol)
        base = self.config.zscore_base_threshold
        k = self.config.dynamic_k
        
        new_threshold = base * (1 + k * volatility)
        
        # 합리적 범위로 제한
        new_threshold = np.clip(new_threshold, base * 0.5, base * 2.0)
        
        self.dynamic_thresholds[symbol] = new_threshold
    
    def normalize_indicator(
        self,
        value: float,
        favorable_direction: str,
        threshold_low: float,
        threshold_high: float
    ) -> float:
        """
        지표 값을 0~1로 정규화
        
        favorable_direction:
        - 'low': 낮을수록 좋음 (RSI < 30, Stoch < 20)
        - 'high': 높을수록 좋음 (Z-Score > 2)
        - 'center': 중앙에서 벗어날수록 좋음 (BB Position)
        """
        if favorable_direction == 'high':
            # 높을수록 좋음
            if value >= threshold_high:
                return 1.0
            elif value <= threshold_low:
                return 0.0
            else:
                return (value - threshold_low) / (threshold_high - threshold_low)
        
        elif favorable_direction == 'low':
            # 낮을수록 좋음
            if value <= threshold_low:
                return 1.0
            elif value >= threshold_high:
                return 0.0
            else:
                return 1.0 - ((value - threshold_low) / (threshold_high - threshold_low))
        
        elif favorable_direction == 'center':
            # 중앙에서 벗어날수록 좋음 (절댓값)
            abs_value = abs(value)
            if abs_value >= threshold_high:
                return 1.0
            elif abs_value <= threshold_low:
                return 0.0
            else:
                return (abs_value - threshold_low) / (threshold_high - threshold_low)
        
        return 0.0
    
    def generate_signal(
        self,
        orderbook: OrderBook,
        current_price: float,
        current_volume: float = 0
    ) -> Tuple[SignalType, float, Dict[str, float]]:
        """
        가중치 기반 신호 생성
        
        Returns:
            (signal_type, signal_score, indicators)
            signal_score: 0~1 사이 값 (가중 합산)
        """
        symbol = orderbook.symbol
        buffer = self._get_buffer(symbol)
        
        # 데이터 추가
        buffer.add_data(current_price, current_volume)
        
        # 지표 계산
        wobi_z = self.calculate_wobi_zscore(orderbook)
        
        if wobi_z is None:
            return SignalType.NONE, 0.0, {}
        
        # 동적 임계값 업데이트
        self.update_dynamic_threshold(symbol)
        z_threshold = self.dynamic_thresholds[symbol]
        
        prices = buffer.get_prices()
        volumes = buffer.get_volumes()
        
        rsi = TechnicalIndicators.calculate_rsi(prices, self.config.rsi_period)
        macd_result = TechnicalIndicators.calculate_macd(
            prices,
            self.config.macd_fast,
            self.config.macd_slow,
            self.config.macd_signal
        )
        bb_result = TechnicalIndicators.calculate_bollinger_bands(
            prices,
            self.config.bb_period,
            self.config.bb_std_dev
        )
        stoch_result = TechnicalIndicators.calculate_stochastic(
            prices,
            self.config.stoch_k_period,
            self.config.stoch_d_period
        )
        volume_ratio = TechnicalIndicators.calculate_volume_ratio(
            volumes,
            self.config.volume_window
        )
        
        # 지표가 준비되지 않으면 대기
        if rsi is None:
            return SignalType.NONE, 0.0, {}
        
        # 각 지표를 0~1로 정규화
        score_wobi = self.normalize_indicator(
            wobi_z, 'high',
            z_threshold * 0.5, z_threshold
        )
        
        score_rsi = self.normalize_indicator(
            rsi, 'low',
            self.config.rsi_oversold, self.config.rsi_overbought
        )
        
        score_macd = 0.0
        if macd_result:
            macd_histogram = macd_result[2]
            # MACD > 0이면 1, < 0이면 0
            score_macd = 1.0 if macd_histogram > 0 else 0.0
        
        score_bb = 0.0
        if bb_result:
            bb_position = bb_result[3]
            # BB 하단 근처일수록 좋음 (-1 ~ 0)
            if bb_position < 0:
                score_bb = abs(bb_position)  # 0~1
        
        score_stoch = 0.0
        if stoch_result:
            stoch_k = stoch_result[0]
            score_stoch = self.normalize_indicator(
                stoch_k, 'low',
                self.config.stoch_oversold, self.config.stoch_overbought
            )
        
        # 가중 합산
        signal_score = (
            self.config.weight_wobi * score_wobi +
            self.config.weight_rsi * score_rsi +
            self.config.weight_macd * score_macd +
            self.config.weight_bb * score_bb +
            self.config.weight_stoch * score_stoch
        )
        
        # 지표 저장
        indicators = {
            'wobi_z': wobi_z,
            'rsi': rsi,
            'macd': macd_result[2] if macd_result else 0,
            'bb_position': bb_result[3] if bb_result else 0,
            'stoch_k': stoch_result[0] if stoch_result else 50,
            'volume_ratio': volume_ratio if volume_ratio else 1.0,
            'score_wobi': score_wobi,
            'score_rsi': score_rsi,
            'score_macd': score_macd,
            'score_bb': score_bb,
            'score_stoch': score_stoch
        }
        
        # 진입 조건: signal_score >= threshold
        if signal_score >= self.config.signal_threshold:
            return SignalType.LONG, signal_score, indicators
        
        return SignalType.NONE, signal_score, indicators
    
    def extract_features(self, symbol: str) -> Optional[np.ndarray]:
        """AI 모델용 피처 추출"""
        buffer = self._get_buffer(symbol)
        
        if not buffer.is_ready(self.config.wobi_window_size):
            return None
        
        wobi_ratios = buffer.get_wobi_ratios()
        prices = buffer.get_prices()
        
        if len(wobi_ratios) < 50:
            return None
        
        features = [
            # W-OBI features (5개)
            wobi_ratios[-1],
            np.mean(wobi_ratios[-10:]),
            np.std(wobi_ratios[-10:]),
            np.mean(wobi_ratios[-50:]),
            wobi_ratios[-1] - wobi_ratios[-10],
            
            # Price features (3개)
            prices[-1],
            prices[-1] / np.mean(prices[-20:]),
            np.std(prices[-20:]) / np.mean(prices[-20:]),
            
            # Technical indicators (3개)
            TechnicalIndicators.calculate_rsi(prices, 14) or 50,
            TechnicalIndicators.calculate_macd(prices, 12, 26, 9)[2] if TechnicalIndicators.calculate_macd(prices, 12, 26, 9) else 0,
            TechnicalIndicators.calculate_bollinger_bands(prices, 20, 2.0)[3] if TechnicalIndicators.calculate_bollinger_bands(prices, 20, 2.0) else 0
        ]
        
        return np.array(features)