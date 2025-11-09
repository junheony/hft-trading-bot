"""
HFT Bot v0.9 - Signal Module with TTL (Time-To-Live)
신호 유효기간을 가진 트레이딩 신호 클래스
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from enum import Enum


class SignalDirection(Enum):
    """신호 방향"""
    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRAL = "NEUTRAL"


class SignalLevel(Enum):
    """신호 레벨 (계층)"""
    MACRO = "MACRO"        # 거시적 필터
    STRATEGIC = "STRATEGIC"  # 전략적 방향성
    TACTICAL = "TACTICAL"    # 전술적 실행


@dataclass
class Signal:
    """
    TTL(Time-To-Live) 지원 트레이딩 신호
    급격한 시장 변화 시 오래된 신호 자동 무효화
    """
    direction: SignalDirection
    score: float  # 0.0 ~ 1.0
    level: SignalLevel
    timestamp: datetime
    ttl_seconds: int  # 유효기간 (초)

    # 메타데이터
    source: str  # 신호 생성 에이전트
    reason: str  # 신호 생성 이유
    metadata: Optional[Dict[str, Any]] = None

    def is_valid(self, current_time: Optional[datetime] = None) -> bool:
        """신호가 아직 유효한지 확인"""
        if current_time is None:
            current_time = datetime.now()

        elapsed = (current_time - self.timestamp).total_seconds()
        return elapsed < self.ttl_seconds

    def remaining_ttl(self, current_time: Optional[datetime] = None) -> float:
        """남은 유효시간 (초)"""
        if current_time is None:
            current_time = datetime.now()

        elapsed = (current_time - self.timestamp).total_seconds()
        remaining = self.ttl_seconds - elapsed
        return max(0.0, remaining)

    def expires_at(self) -> datetime:
        """만료 시각"""
        return self.timestamp + timedelta(seconds=self.ttl_seconds)

    @classmethod
    def no_signal(cls, level: SignalLevel, source: str, reason: str = "No opportunity") -> 'Signal':
        """진입 불가 신호"""
        return cls(
            direction=SignalDirection.NEUTRAL,
            score=0.0,
            level=level,
            timestamp=datetime.now(),
            ttl_seconds=0,
            source=source,
            reason=reason
        )

    def __repr__(self) -> str:
        valid_status = "VALID" if self.is_valid() else "EXPIRED"
        return (
            f"Signal({self.direction.value}, score={self.score:.3f}, "
            f"level={self.level.value}, {valid_status}, "
            f"TTL={self.remaining_ttl():.1f}s, source={self.source})"
        )


@dataclass
class ExecutionSignal(Signal):
    """
    실행 신호 (Tactical Level)
    포지션 사이즈 정보 포함
    """
    position_size_krw: float = 0.0  # 진입 금액
    expected_slippage: float = 0.0  # 예상 슬리피지

    @classmethod
    def create(
        cls,
        direction: SignalDirection,
        score: float,
        position_size_krw: float,
        source: str,
        reason: str,
        ttl_seconds: int = 30,
        expected_slippage: float = 0.0
    ) -> 'ExecutionSignal':
        """실행 신호 생성"""
        return cls(
            direction=direction,
            score=score,
            level=SignalLevel.TACTICAL,
            timestamp=datetime.now(),
            ttl_seconds=ttl_seconds,
            source=source,
            reason=reason,
            position_size_krw=position_size_krw,
            expected_slippage=expected_slippage
        )
