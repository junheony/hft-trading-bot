"""
HFT Bot v0.8 - Advanced Backtester Module
정확한 체결 모델 및 수수료/슬리피지 반영 백테스트 엔진
"""

import glob
import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, List, Optional

import numpy as np

from core import (
    TradingConfig,
    OrderBook,
    SignalType,
    ExitReason,
    Trade,
    Logger,
)
from strategy import WeightedMultiStrategy


@dataclass
class BacktestPosition:
    entry_time: datetime
    entry_index: int
    entry_price: float
    amount: float
    entry_fee: float
    highest_price: float
    signal_score: float
    indicators: Dict[str, float]


class Backtester:
    """
    백테스트 엔진 (v0.8)
    - JSONL 실데이터 재생
    - 슬리피지/수수료 반영 체결 모델
    - 동일한 전략 파이프라인 재사용
    """

    def __init__(self, config: TradingConfig, logger: Logger):
        self.config = config
        self.logger = logger
        self.strategy = WeightedMultiStrategy(config)

    def load_data(self, symbol: str) -> List[Dict[str, Any]]:
        """수집된 JSONL 데이터 로드"""
        pattern = os.path.join(
            self.config.backtest_data_dir,
            f"{symbol.replace('/', '_')}_*.jsonl",
        )
        files = sorted(glob.glob(pattern))

        if not files:
            raise FileNotFoundError(f"No data for {symbol}")

        dataset: List[Dict[str, Any]] = []
        with open(files[0], "r", encoding="utf-8") as f:
            for line in f:
                try:
                    item = json.loads(line)
                    if item.get("type") == "orderbook":
                        dataset.append(item)
                except json.JSONDecodeError:
                    continue

        return dataset

    def run(self, symbol: str, use_test_data: bool = True) -> Dict[str, Any]:
        """백테스트 실행"""
        self.logger.info("=" * 60)
        self.logger.info(f"[Backtester v0.8] {symbol}")
        self.logger.info("=" * 60)

        records = self.load_data(symbol)
        total_ticks = len(records)
        if total_ticks == 0:
            raise RuntimeError("No usable ticks in dataset")

        split_idx = int(total_ticks * self.config.backtest_train_ratio)
        playback = records[split_idx:] if use_test_data else records

        self.logger.info(f"Ticks loaded : {total_ticks}")
        self.logger.info(
            f"Ticks used   : {len(playback)} ({'TEST' if use_test_data else 'ALL'})"
        )

        trades: List[Trade] = []
        position: Optional[BacktestPosition] = None

        for idx, record in enumerate(playback):
            data = record["data"]
            timestamp = datetime.fromisoformat(record["timestamp"])

            orderbook = OrderBook(
                timestamp=timestamp,
                symbol=symbol,
                bids=data["bids"][: self.config.orderbook_depth],
                asks=data["asks"][: self.config.orderbook_depth],
            )

            current_price = data["price"]
            current_volume = data.get("volume", 0)

            signal, signal_score, indicators = self.strategy.generate_signal(
                orderbook, current_price, current_volume
            )

            if position is None and signal == SignalType.LONG:
                ask_price = orderbook.asks[0][0]
                entry_price = ask_price * (
                    1 + self.config.slippage_bps / 10_000
                )
                amount = self.config.trade_amount_krw / entry_price
                entry_cost = amount * entry_price
                entry_fee = entry_cost * self.config.taker_fee

                position = BacktestPosition(
                    entry_time=timestamp,
                    entry_index=idx,
                    entry_price=entry_price,
                    amount=amount,
                    entry_fee=entry_fee,
                    highest_price=current_price,
                    signal_score=signal_score,
                    indicators=indicators,
                )
                continue

            if position is None:
                continue

            # 업데이트
            if self.config.trailing_stop and current_price > position.highest_price:
                position.highest_price = current_price

            bid_price = orderbook.bids[0][0]
            exit_price = bid_price * (1 - self.config.slippage_bps / 10_000)

            pnl_rate = (exit_price - position.entry_price) / position.entry_price
            holding_seconds = (timestamp - position.entry_time).total_seconds()

            exit_reason: Optional[ExitReason] = None
            if pnl_rate >= self.config.take_profit_rate:
                exit_reason = ExitReason.TAKE_PROFIT
            elif pnl_rate <= -self.config.stop_loss_rate:
                exit_reason = ExitReason.STOP_LOSS
            elif (
                self.config.trailing_stop
                and position.highest_price > 0
                and (position.highest_price - current_price)
                / position.highest_price
                >= self.config.trailing_stop_pct
            ):
                exit_reason = ExitReason.TRAILING_STOP
            elif holding_seconds > self.config.time_cut_seconds:
                exit_reason = ExitReason.TIME_CUT

            if not exit_reason:
                continue

            exit_cost = exit_price * position.amount
            exit_fee = exit_cost * self.config.taker_fee
            gross_pnl = (exit_price - position.entry_price) * position.amount
            net_pnl = gross_pnl - position.entry_fee - exit_fee

            trade = Trade(
                trade_id=f"bt_{len(trades)+1}",
                symbol=symbol,
                side=SignalType.LONG,
                entry_time=position.entry_time,
                exit_time=timestamp,
                entry_price=position.entry_price,
                exit_price=exit_price,
                amount=position.amount,
                pnl=net_pnl,
                exit_reason=exit_reason,
                holding_seconds=holding_seconds,
                signal_score=position.signal_score,
                indicators=position.indicators,
            )
            trades.append(trade)
            position = None

        stats = self._calculate_statistics(trades)
        stats["trades"] = trades
        return stats

    def _calculate_statistics(self, trades: List[Trade]) -> Dict[str, Any]:
        if not trades:
            self.logger.warning("No trades executed")
            return {"error": "No trades"}

        pnls = np.array([t.pnl for t in trades])
        wins = pnls[pnls > 0]
        losses = pnls[pnls <= 0]

        total_pnl = float(np.sum(pnls))
        total_trades = len(trades)
        win_rate = len(wins) / total_trades
        avg_win = float(np.mean(wins)) if wins.size else 0.0
        avg_loss = float(np.mean(losses)) if losses.size else 0.0

        mean_return = np.mean(pnls)
        std_return = np.std(pnls)
        sharpe = float((mean_return / std_return) * np.sqrt(252)) if std_return > 0 else 0.0

        cumulative = np.cumsum(pnls)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = cumulative - running_max
        max_drawdown = float(drawdown.min()) if drawdown.size else 0.0
        max_running = running_max.max() if running_max.size else 0.0
        max_drawdown_pct = float((max_drawdown / max_running) * 100) if max_running > 0 else 0.0

        total_wins = float(np.sum(wins)) if wins.size else 0.0
        total_losses = float(abs(np.sum(losses))) if losses.size else 0.0
        profit_factor = total_wins / total_losses if total_losses > 0 else 0.0

        avg_holding = float(np.mean([t.holding_seconds for t in trades]))
        exit_reasons: Dict[str, int] = {}
        for trade in trades:
            key = trade.exit_reason.value
            exit_reasons[key] = exit_reasons.get(key, 0) + 1

        stats = {
            "total_trades": total_trades,
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "sharpe_ratio": sharpe,
            "max_drawdown": max_drawdown,
            "max_drawdown_pct": max_drawdown_pct,
            "profit_factor": profit_factor,
            "avg_holding_seconds": avg_holding,
            "exit_reasons": exit_reasons,
        }

        self.logger.info("=" * 60)
        self.logger.info("BACKTEST RESULTS (v0.8)")
        self.logger.info("=" * 60)
        self.logger.info(f"Trades         : {total_trades}")
        self.logger.info(f"Win Rate       : {win_rate*100:.1f}%")
        self.logger.info(f"Total PnL      : {total_pnl:,.0f} KRW")
        self.logger.info(f"Avg Win / Loss : {avg_win:,.0f} / {avg_loss:,.0f}")
        self.logger.info(f"Sharpe Ratio   : {sharpe:.3f}")
        self.logger.info(
            f"Max Drawdown   : {max_drawdown:,.0f} KRW ({max_drawdown_pct:.1f}%)"
        )
        self.logger.info(f"Profit Factor  : {profit_factor:.2f}")
        self.logger.info(f"Avg Holding    : {avg_holding:.1f}s")
        self.logger.info(f"Exit Reasons   : {exit_reasons}")
        self.logger.info("=" * 60)

        return stats
