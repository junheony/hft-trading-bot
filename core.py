"""
HFT Bot v0.7 - Core Module
데이터 모델 및 설정
"""

import os
from datetime import datetime
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

# ============================================================================
# Enums
# ============================================================================

class ExchangeType(Enum):
    """지원 거래소"""
    BITHUMB = "bithumb"
    UPBIT = "upbit"
    COINONE = "coinone"


class SignalType(Enum):
    """신호 타입"""
    NONE = "NONE"
    LONG = "LONG"
    # SHORT는 현재 비활성화 (안정성 우선)


class ExitReason(Enum):
    """청산 사유"""
    TAKE_PROFIT = "TP"
    STOP_LOSS = "SL"
    TIME_CUT = "TC"
    TRAILING_STOP = "TS"
    DAILY_LIMIT = "DL"
    MANUAL = "MANUAL"
    EMERGENCY = "EMERGENCY"


# ============================================================================
# Configuration
# ============================================================================

@dataclass
class TradingConfig:
    """거래 설정 (모든 파라미터)"""
    
    # Exchange
    exchange_type: ExchangeType = ExchangeType.BITHUMB
    symbols: List[str] = field(default_factory=lambda: ["BTC/KRW"])
    
    # Trading
    trade_amount_krw: float = 500_000
    orderbook_depth: int = 10
    slippage_bps: float = 1.5
    
    # === Strategy Weights (가중치 기반) ===
    # 총합 1.0이 되도록 설정
    weight_wobi: float = 0.35      # W-OBI
    weight_rsi: float = 0.25       # RSI
    weight_macd: float = 0.20      # MACD
    weight_bb: float = 0.10        # Bollinger Bands
    weight_stoch: float = 0.10     # Stochastic
    signal_threshold: float = 0.6  # 0.6 이상이면 진입
    
    # W-OBI
    wobi_window_size: int = 100
    zscore_base_threshold: float = 2.0
    
    # RSI
    rsi_period: int = 14
    rsi_overbought: float = 70
    rsi_oversold: float = 30
    
    # MACD (정확한 EMA)
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    
    # Bollinger Bands
    bb_period: int = 20
    bb_std_dev: float = 2.0
    
    # Stochastic
    stoch_k_period: int = 14
    stoch_d_period: int = 3
    stoch_overbought: float = 80
    stoch_oversold: float = 20
    
    # Volume
    volume_window: int = 20
    volume_threshold: float = 1.5
    
    # Exit
    take_profit_rate: float = 0.0015
    stop_loss_rate: float = 0.001
    time_cut_seconds: int = 60
    trailing_stop: bool = False
    trailing_stop_pct: float = 0.0005
    
    # Fees (거래소별 정확한 수수료)
    maker_fee: float = 0.0025
    taker_fee: float = 0.0025
    
    # Risk
    max_daily_loss: float = -100_000
    max_consecutive_losses: int = 5
    max_positions: int = 3
    max_position_size: float = 1_000_000
    
    # Dynamic (연속 함수)
    enable_dynamic_params: bool = True
    volatility_window: int = 100
    dynamic_k: float = 2.0  # z_threshold = base * (1 + k * volatility)
    
    # AI
    use_ai_filter: bool = True
    ai_confidence_threshold: float = 0.6
    ai_model_path: str = "models/mlp_model.pkl"
    
    # Telegram
    telegram_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    
    # Backtest
    backtest_data_dir: str = "data/collected"
    backtest_train_ratio: float = 0.7
    
    # System
    entry_retry_max: int = 3
    entry_retry_delay: float = 1.0  # seconds
    exit_retry_max: int = 5
    exit_retry_delay: float = 0.5


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class OrderBook:
    """오더북"""
    timestamp: datetime
    symbol: str
    bids: List[Tuple[float, float]]
    asks: List[Tuple[float, float]]
    
    @property
    def mid_price(self) -> float:
        return (self.asks[0][0] + self.bids[0][0]) / 2
    
    @property
    def spread_bps(self) -> float:
        return (self.asks[0][0] - self.bids[0][0]) / self.mid_price * 10000
    
    def liquidity_check(self, krw_amount: float) -> bool:
        """유동성 체크"""
        total_ask_liquidity = sum(p * a for p, a in self.asks[:5])
        return total_ask_liquidity >= krw_amount * 1.5


@dataclass
class Position:
    """포지션"""
    position_id: str
    symbol: str
    side: SignalType
    entry_time: datetime
    entry_price: float
    amount: float
    entry_fee: float
    
    # Strategy
    signal_score: float
    indicators: Dict[str, float] = field(default_factory=dict)
    
    # Trailing
    highest_price: float = 0.0


@dataclass
class Trade:
    """거래 기록"""
    trade_id: str
    symbol: str
    side: SignalType
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    amount: float
    pnl: float
    exit_reason: ExitReason
    holding_seconds: float
    signal_score: float
    indicators: Dict[str, float] = field(default_factory=dict)


# ============================================================================
# Logger
# ============================================================================

import csv
import json

class Logger:
    """통합 로거"""
    
    def __init__(self, name: str = "hft_v07"):
        self.name = name
        os.makedirs("logs", exist_ok=True)
        os.makedirs("data", exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = f"logs/{name}_{timestamp}.log"
        self.trade_csv = f"data/trades_{timestamp}.csv"
        self.trade_jsonl = f"data/trades_{timestamp}.jsonl"
        
        with open(self.trade_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp', 'trade_id', 'symbol', 'side', 'event',
                'price', 'amount', 'pnl', 'exit_reason', 'holding_seconds',
                'signal_score', 'wobi_z', 'rsi', 'macd', 'bb_pos', 'stoch'
            ])
    
    def _write(self, level: str, msg: str):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        line = f"[{ts}] {level:8} | {msg}\n"
        print(line.strip())
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(line)
    
    def info(self, msg: str): self._write("INFO", msg)
    def warning(self, msg: str): self._write("WARNING", msg)
    def error(self, msg: str): self._write("ERROR", msg)
    def trade(self, msg: str): self._write("TRADE", msg)
    
    def log_entry(self, position: Position):
        ind = position.indicators
        self.trade(
            f"🟢 ENTRY | {position.symbol} | "
            f"Score: {position.signal_score:.3f} | "
            f"Price: {position.entry_price:,.0f} | "
            f"Z: {ind.get('wobi_z', 0):.2f} | RSI: {ind.get('rsi', 0):.1f}"
        )
        
        with open(self.trade_jsonl, 'a', encoding='utf-8') as f:
            f.write(json.dumps({
                'timestamp': position.entry_time.isoformat(),
                'event': 'ENTRY',
                'data': {
                    'position_id': position.position_id,
                    'symbol': position.symbol,
                    'price': position.entry_price,
                    'amount': position.amount,
                    'score': position.signal_score,
                    'indicators': position.indicators
                }
            }, ensure_ascii=False) + '\n')
        
        with open(self.trade_csv, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                position.entry_time.isoformat(), position.position_id,
                position.symbol, position.side.value, 'ENTRY',
                position.entry_price, position.amount, None, None, None,
                position.signal_score, ind.get('wobi_z'), ind.get('rsi'),
                ind.get('macd'), ind.get('bb_position'), ind.get('stoch_k')
            ])
    
    def log_exit(self, trade: Trade):
        emoji = "📈" if trade.pnl > 0 else "📉"
        self.trade(
            f"🔴 EXIT | {trade.symbol} | "
            f"PnL: {trade.pnl:,.0f} KRW {emoji} | "
            f"Reason: {trade.exit_reason.value}"
        )
        
        with open(self.trade_jsonl, 'a', encoding='utf-8') as f:
            f.write(json.dumps({
                'timestamp': trade.exit_time.isoformat(),
                'event': 'EXIT',
                'data': {
                    'trade_id': trade.trade_id,
                    'pnl': trade.pnl,
                    'exit_reason': trade.exit_reason.value
                }
            }, ensure_ascii=False) + '\n')
        
        with open(self.trade_csv, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                trade.exit_time.isoformat(), trade.trade_id,
                trade.symbol, trade.side.value, 'EXIT',
                trade.exit_price, trade.amount, trade.pnl,
                trade.exit_reason.value, trade.holding_seconds,
                None, None, None, None, None, None
            ])
