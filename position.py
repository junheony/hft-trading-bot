"""
HFT Bot v0.7 - Position Manager Module
원자적 포지션 관리
"""

import asyncio
from typing import Dict, List, Optional
from datetime import datetime

from core import Position, Trade, TradingConfig, SignalType, ExitReason


class PositionManager:
    """
    Thread-Safe 포지션 관리자
    - asyncio.Lock으로 Race Condition 완전 방지
    - 트레일링 스톱 지원
    """
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.lock = asyncio.Lock()
        self.positions: Dict[str, Position] = {}
    
    def get_position_count(self) -> int:
        """현재 포지션 수"""
        return len(self.positions)
    
    def has_position_for_symbol(self, symbol: str) -> bool:
        """특정 심볼의 포지션 보유 여부"""
        return any(p.symbol == symbol for p in self.positions.values())
    
    async def open_position(self, position: Position) -> Position:
        """포지션 오픈 (원자적)"""
        async with self.lock:
            if position.position_id in self.positions:
                raise ValueError(f"Position {position.position_id} already exists")
            
            self.positions[position.position_id] = position
            return position
    
    async def close_position(
        self,
        position_id: str,
        exit_price: float,
        exit_fee: float,
        exit_reason: ExitReason
    ) -> Trade:
        """포지션 청산 (원자적)"""
        async with self.lock:
            if position_id not in self.positions:
                raise ValueError(f"Position {position_id} not found")
            
            pos = self.positions[position_id]
            
            # PnL 계산
            if pos.side == SignalType.LONG:
                gross_pnl = (exit_price - pos.entry_price) * pos.amount
            else:
                # SHORT (현재 비활성화)
                gross_pnl = (pos.entry_price - exit_price) * pos.amount
            
            net_pnl = gross_pnl - pos.entry_fee - exit_fee
            
            trade = Trade(
                trade_id=pos.position_id,
                symbol=pos.symbol,
                side=pos.side,
                entry_time=pos.entry_time,
                exit_time=datetime.now(),
                entry_price=pos.entry_price,
                exit_price=exit_price,
                amount=pos.amount,
                pnl=net_pnl,
                exit_reason=exit_reason,
                holding_seconds=(datetime.now() - pos.entry_time).total_seconds(),
                signal_score=pos.signal_score,
                indicators=pos.indicators
            )
            
            del self.positions[position_id]
            return trade
    
    def update_trailing_stop(self, position_id: str, current_price: float):
        """트레일링 스톱 업데이트"""
        if position_id not in self.positions:
            return
        
        pos = self.positions[position_id]
        
        if pos.side == SignalType.LONG:
            if current_price > pos.highest_price:
                pos.highest_price = current_price
    
    def check_trailing_stop(self, position_id: str, current_price: float) -> bool:
        """트레일링 스톱 조건 체크"""
        if not self.config.trailing_stop:
            return False
        
        if position_id not in self.positions:
            return False
        
        pos = self.positions[position_id]
        
        if pos.side == SignalType.LONG:
            if pos.highest_price == 0:
                return False
            
            drop_rate = (pos.highest_price - current_price) / pos.highest_price
            return drop_rate >= self.config.trailing_stop_pct
        
        return False
    
    def get_all_positions(self) -> List[Position]:
        """모든 포지션 조회"""
        return list(self.positions.values())
    
    def get_position(self, position_id: str) -> Optional[Position]:
        """특정 포지션 조회"""
        return self.positions.get(position_id)