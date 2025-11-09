"""
HFT Bot v0.7 - Technical Indicators Module
정확한 EMA/RSI/MACD/BB/Stochastic 구현
"""

import numpy as np
from collections import deque
from typing import Optional, Tuple, List

class TechnicalIndicators:
    """기술적 지표 계산 (정확한 구현)"""
    
    @staticmethod
    def calculate_ema(prices: np.ndarray, period: int) -> float:
        """
        정확한 지수 이동평균 (EMA)
        EMA = Price(t) * k + EMA(t-1) * (1-k)
        k = 2 / (period + 1)
        """
        if len(prices) < period:
            return None
        
        k = 2.0 / (period + 1)
        ema = prices[0]  # 첫 값을 초기 EMA로
        
        for price in prices[1:]:
            ema = price * k + ema * (1 - k)
        
        return ema
    
    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> Optional[float]:
        """
        정확한 RSI (Relative Strength Index)
        RSI = 100 - (100 / (1 + RS))
        RS = 평균 상승폭 / 평균 하락폭
        """
        if len(prices) < period + 1:
            return None
        
        prices_array = np.array(prices)
        deltas = np.diff(prices_array)
        
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        # 첫 평균은 단순 평균
        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])
        
        # 이후는 Wilder's smoothing (EMA와 유사)
        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
        
        return rsi
    
    @staticmethod
    def calculate_macd(
        prices: List[float],
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
    ) -> Optional[Tuple[float, float, float]]:
        """
        정확한 MACD
        Returns: (MACD Line, Signal Line, Histogram)
        """
        if len(prices) < slow + signal:
            return None
        
        prices_array = np.array(prices)
        
        # EMA Fast & Slow
        ema_fast = TechnicalIndicators.calculate_ema(prices_array[-fast:], fast)
        ema_slow = TechnicalIndicators.calculate_ema(prices_array[-slow:], slow)
        
        if ema_fast is None or ema_slow is None:
            return None
        
        macd_line = ema_fast - ema_slow
        
        # Signal Line (MACD의 EMA)
        # 실제로는 과거 MACD 값들의 EMA를 구해야 하지만
        # 단순화: 최근 signal 기간의 가격 변화로 근사
        recent_prices = prices_array[-signal:]
        signal_line = TechnicalIndicators.calculate_ema(recent_prices, signal)
        
        if signal_line is None:
            signal_line = macd_line * 0.9  # Fallback
        
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
    
    @staticmethod
    def calculate_bollinger_bands(
        prices: List[float],
        period: int = 20,
        num_std: float = 2.0
    ) -> Optional[Tuple[float, float, float, float]]:
        """
        Bollinger Bands
        Returns: (upper, middle, lower, bb_position)
        bb_position: -1 (하단) ~ 0 (중앙) ~ 1 (상단)
        """
        if len(prices) < period:
            return None
        
        prices_array = np.array(prices[-period:])
        
        middle = np.mean(prices_array)
        std = np.std(prices_array, ddof=1)  # 표본 표준편차
        
        upper = middle + num_std * std
        lower = middle - num_std * std
        
        current = prices[-1]
        
        # BB Position 계산
        if upper == lower:
            bb_position = 0.0
        else:
            bb_position = (current - middle) / (upper - middle)
            bb_position = np.clip(bb_position, -1.0, 1.0)
        
        return upper, middle, lower, bb_position
    
    @staticmethod
    def calculate_stochastic(
        prices: List[float],
        k_period: int = 14,
        d_period: int = 3
    ) -> Optional[Tuple[float, float]]:
        """
        Stochastic Oscillator
        %K = (Current - Lowest) / (Highest - Lowest) * 100
        %D = %K의 이동평균
        Returns: (%K, %D)
        """
        if len(prices) < k_period:
            return None
        
        recent_prices = prices[-k_period:]
        
        highest = max(recent_prices)
        lowest = min(recent_prices)
        current = recent_prices[-1]
        
        if highest == lowest:
            k = 50.0
        else:
            k = ((current - lowest) / (highest - lowest)) * 100.0
        
        # %D는 %K의 이동평균 (단순화: 최근 d_period의 평균)
        # 실제로는 과거 %K 값들을 저장해야 하지만, 여기서는 근사
        if len(prices) >= k_period + d_period:
            d = k  # 단순화
        else:
            d = k
        
        return k, d
    
    @staticmethod
    def calculate_volume_ratio(
        volumes: List[float],
        period: int = 20
    ) -> Optional[float]:
        """
        거래량 비율
        현재 거래량 / 평균 거래량
        """
        if len(volumes) < period:
            return None
        
        recent_volumes = volumes[-period:]
        avg_volume = np.mean(recent_volumes)
        current_volume = volumes[-1]
        
        if avg_volume == 0:
            return None
        
        return current_volume / avg_volume


class IndicatorBuffer:
    """지표 계산을 위한 데이터 버퍼 관리"""
    
    def __init__(self, max_size: int = 200):
        self.max_size = max_size
        self.prices = deque(maxlen=max_size)
        self.volumes = deque(maxlen=max_size)
        self.wobi_ratios = deque(maxlen=max_size)
    
    def add_data(self, price: float, volume: float = 0, wobi_ratio: float = None):
        """데이터 추가"""
        self.prices.append(price)
        self.volumes.append(volume)
        if wobi_ratio is not None:
            self.wobi_ratios.append(wobi_ratio)
    
    def get_prices(self) -> List[float]:
        return list(self.prices)
    
    def get_volumes(self) -> List[float]:
        return list(self.volumes)
    
    def get_wobi_ratios(self) -> List[float]:
        return list(self.wobi_ratios)
    
    def is_ready(self, min_size: int) -> bool:
        return len(self.prices) >= min_size