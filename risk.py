"""
HFT Bot v0.9 - Risk Management Module
Dynamic Position Sizing + Emergency Controls
"""

from datetime import datetime, date
from typing import Tuple, Dict, Any, List
import numpy as np

from core import TradingConfig, Trade, Position


class RiskManager:
    """
    리스크 관리 시스템 v0.9
    - 일일 손실 한도
    - 연속 손실 제한
    - 동적 포지션 사이징 (변동성 + 신뢰도 기반)
    - 긴급 중지
    """

    def __init__(self, config: TradingConfig):
        self.config = config
        self.reset_daily_stats()
        self.emergency_stop = False
        self.emergency_reason = ""
        self.active_positions: List[Position] = []  # 현재 활성 포지션
    
    def reset_daily_stats(self):
        """일일 통계 초기화"""
        self.today: date = datetime.now().date()
        self.daily_pnl: float = 0.0
        self.daily_trades: int = 0
        self.consecutive_losses: int = 0
        self.daily_wins: int = 0
        self.daily_losses: int = 0
        self.peak_pnl: float = 0.0
        self.trades_history: list = []
    
    def check_daily_reset(self):
        """날짜 변경 체크"""
        if datetime.now().date() > self.today:
            self.reset_daily_stats()
    
    def can_enter_position(
        self,
        current_positions: int,
        estimated_cost: float
    ) -> Tuple[bool, str]:
        """
        진입 가능 여부 체크
        
        Returns:
            (can_enter, reason)
        """
        self.check_daily_reset()
        
        # 긴급 중지
        if self.emergency_stop:
            return False, "⛔ EMERGENCY STOP ACTIVATED"
        
        # 일일 손실 한도
        if self.daily_pnl < self.config.max_daily_loss:
            return False, f"⛔ Daily loss limit: {self.daily_pnl:,.0f} KRW"
        
        # 연속 손실
        if self.consecutive_losses >= self.config.max_consecutive_losses:
            return False, f"⛔ {self.consecutive_losses} consecutive losses"
        
        # 동시 포지션 수
        if current_positions >= self.config.max_positions:
            return False, f"⛔ Max {self.config.max_positions} positions"
        
        # 포지션 크기
        if estimated_cost > self.config.max_position_size:
            return False, f"⛔ Position too large: {estimated_cost:,.0f}"
        
        return True, "✅ OK"
    
    def record_trade(self, trade: Trade):
        """거래 기록"""
        self.daily_pnl += trade.pnl
        self.daily_trades += 1
        self.trades_history.append(trade)
        
        if trade.pnl > 0:
            self.daily_wins += 1
            self.consecutive_losses = 0
            self.peak_pnl = max(self.peak_pnl, self.daily_pnl)
        else:
            self.daily_losses += 1
            self.consecutive_losses += 1
        
        # 일일 손실 한도 체크 (자동 중지)
        if self.daily_pnl < self.config.max_daily_loss:
            self.emergency_stop = True
    
    def get_daily_stats(self) -> Dict[str, Any]:
        """일일 통계"""
        return {
            'date': self.today.isoformat(),
            'pnl': self.daily_pnl,
            'peak_pnl': self.peak_pnl,
            'drawdown': self.daily_pnl - self.peak_pnl,
            'trades': self.daily_trades,
            'wins': self.daily_wins,
            'losses': self.daily_losses,
            'win_rate': self.daily_wins / max(self.daily_trades, 1),
            'consecutive_losses': self.consecutive_losses,
            'emergency_stop': self.emergency_stop,
            'sharpe_ratio': self.calculate_sharpe_ratio()
        }
    
    def calculate_sharpe_ratio(self) -> float:
        """Sharpe Ratio 추정"""
        if len(self.trades_history) < 2:
            return 0.0
        
        pnls = [t.pnl for t in self.trades_history]
        mean_return = np.mean(pnls)
        std_return = np.std(pnls)
        
        if std_return == 0:
            return 0.0
        
        # 연율화 (252 거래일 가정)
        sharpe = (mean_return / std_return) * np.sqrt(252)
        
        return sharpe
    
    def calculate_position_size(self, volatility: float, confidence: float) -> float:
        """
        동적 포지션 사이징 (v0.9)

        Args:
            volatility: 최근 가격 변동성 (0.0 ~ 1.0)
            confidence: 신호 신뢰도 (0.0 ~ 1.0)

        Returns:
            포지션 크기 (KRW)

        전략:
            - 변동성 높으면 → 포지션 축소 (리스크 감소)
            - 신호 약하면 → 포지션 축소 (확신 부족)
            - Sharpe Ratio 좋으면 → 포지션 증가 (성과 좋음)
        """
        base_size = self.config.trade_amount_krw

        # 1. 변동성 조정 (높을수록 축소)
        # 기준: 0.02 (2%) 변동성 = 1.0 factor
        target_volatility = 0.02
        if volatility > 0:
            volatility_factor = min(1.0, target_volatility / volatility)
        else:
            volatility_factor = 1.0

        # 2. 신뢰도 조정
        confidence_factor = confidence

        # 3. Sharpe Ratio 조정 (성과 기반)
        sharpe = self.calculate_sharpe_ratio()
        if len(self.trades_history) >= 10:
            if sharpe > 1.5:
                sharpe_factor = 1.2  # 성과 좋으면 20% 증가
            elif sharpe > 1.0:
                sharpe_factor = 1.1
            elif sharpe < 0:
                sharpe_factor = 0.7  # 성과 나쁘면 30% 감소
            else:
                sharpe_factor = 1.0
        else:
            sharpe_factor = 1.0  # 초기에는 조정 없음

        # 4. 연속 손실 조정
        if self.consecutive_losses >= 3:
            consecutive_factor = 0.5  # 연속 손실 시 50% 축소
        elif self.consecutive_losses >= 2:
            consecutive_factor = 0.75
        else:
            consecutive_factor = 1.0

        # 최종 포지션 크기
        position_size = (
            base_size *
            volatility_factor *
            confidence_factor *
            sharpe_factor *
            consecutive_factor
        )

        # 최소/최대 한도
        min_size = base_size * 0.2  # 최소 20%
        max_size = min(base_size * 1.5, self.config.max_position_size)  # 최대 150%

        position_size = max(min_size, min(position_size, max_size))

        return position_size

    def activate_emergency_stop(self, reason: str):
        """긴급 중지 활성화"""
        self.emergency_stop = True
        self.emergency_reason = reason
        print(f"\n{'='*60}")
        print(f"🚨 EMERGENCY STOP ACTIVATED")
        print(f"Reason: {reason}")
        print(f"{'='*60}\n")

    def deactivate_emergency_stop(self):
        """긴급 중지 해제 (수동)"""
        self.emergency_stop = False
        self.emergency_reason = ""
        print("✅ Emergency stop deactivated")
