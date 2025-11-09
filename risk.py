"""
HFT Bot v0.7 - Risk Management Module
"""

from datetime import datetime, date
from typing import Tuple, Dict, Any
import numpy as np

from core import TradingConfig, Trade


class RiskManager:
    """
    리스크 관리 시스템
    - 일일 손실 한도
    - 연속 손실 제한
    - 포지션 크기 제한
    - 긴급 중지
    """
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.reset_daily_stats()
        self.emergency_stop = False
    
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
            'emergency_stop': self.emergency_stop
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
    
    def activate_emergency_stop(self, reason: str):
        """긴급 중지 활성화"""
        self.emergency_stop = True
        print(f"\n{'='*60}")
        print(f"🚨 EMERGENCY STOP ACTIVATED")
        print(f"Reason: {reason}")
        print(f"{'='*60}\n")
    
    def deactivate_emergency_stop(self):
        """긴급 중지 해제 (수동)"""
        self.emergency_stop = False
        print("✅ Emergency stop deactivated")