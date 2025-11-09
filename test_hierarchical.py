"""
HFT Bot v0.9 - Hierarchical Strategy Test
계층적 에이전트 시스템 테스트
"""

import numpy as np
from datetime import datetime

from core import TradingConfig, OrderBook, Logger
from risk import RiskManager
from hierarchical_strategy import HierarchicalStrategy
from signal import SignalDirection


def create_mock_orderbook(symbol: str = "BTC/KRW", base_price: float = 50_000_000) -> OrderBook:
    """모의 오더북 생성"""
    bids = [(base_price - i * 1000, 0.1) for i in range(1, 11)]
    asks = [(base_price + i * 1000, 0.1) for i in range(1, 11)]

    return OrderBook(
        timestamp=datetime.now(),
        symbol=symbol,
        bids=bids,
        asks=asks
    )


def test_hierarchical_strategy():
    """계층적 전략 테스트"""
    print("=" * 80)
    print("HFT Bot v0.9 - Hierarchical Strategy Test")
    print("=" * 80)
    print()

    # 설정
    config = TradingConfig(
        symbols=["BTC/KRW"],
        trade_amount_krw=500_000,
        signal_threshold=0.6,
        take_profit_rate=0.0015,
        stop_loss_rate=0.001,
    )

    logger = Logger("test_hierarchical")
    risk_manager = RiskManager(config)
    strategy = HierarchicalStrategy(config, risk_manager, logger)

    print("✓ Hierarchical Strategy initialized")
    print(f"  - Macro Agent: {strategy.macro_agent.__class__.__name__}")
    print(f"  - Strategy Agent: {strategy.strategy_agent.__class__.__name__}")
    print(f"  - Execution Agent: {strategy.execution_agent.__class__.__name__}")
    print()

    # === Test 1: 데이터 부족 (초기 상태) ===
    print("[Test 1] Initial State (Insufficient Data)")
    print("-" * 80)

    orderbook = create_mock_orderbook()
    signal, metadata = strategy.generate_signal(orderbook, 50_000_000, 100)

    print(f"Signal: {signal}")
    print(f"Macro: {metadata['macro_signal']}")
    print()

    # === Test 2: 데이터 축적 (50틱) ===
    print("[Test 2] Accumulating Data (50 ticks)")
    print("-" * 80)

    base_price = 50_000_000
    for i in range(50):
        # 가격 변동 시뮬레이션
        noise = np.random.randn() * 10000
        price = base_price + noise
        volume = np.random.uniform(50, 150)

        orderbook = create_mock_orderbook(base_price=price)
        signal, metadata = strategy.generate_signal(orderbook, price, volume)

        if i % 10 == 0:
            print(f"  Tick {i+1}/50: price={price:,.0f}, signal={signal is not None}")

    print()

    # === Test 3: 정상 신호 생성 ===
    print("[Test 3] Signal Generation with Full Data")
    print("-" * 80)

    # 강한 매수 압력 시뮬레이션
    price = 50_000_000
    orderbook = OrderBook(
        timestamp=datetime.now(),
        symbol="BTC/KRW",
        bids=[(price - i * 1000, 1.0 + i * 0.1) for i in range(1, 11)],  # 강한 매수
        asks=[(price + i * 1000, 0.1) for i in range(1, 11)]  # 약한 매도
    )

    signal, metadata = strategy.generate_signal(orderbook, price, 100)

    print(f"\nFinal Signal: {signal}")
    print()

    if signal:
        print("Signal Details:")
        print(f"  Direction: {signal.direction.value}")
        print(f"  Score: {signal.score:.3f}")
        print(f"  Position Size: {signal.position_size_krw:,.0f} KRW")
        print(f"  Expected Slippage: {signal.expected_slippage:.4%}")
        print(f"  TTL: {signal.ttl_seconds}s")
        print(f"  Reason: {signal.reason}")
        print()

    print("Metadata:")
    print(f"  Macro Score: {metadata['macro_signal']['score']:.3f}")
    if 'strategic_signal' in metadata:
        print(f"  Strategic Score: {metadata['strategic_signal']['score']:.3f}")
        print(f"  Strategic Direction: {metadata['strategic_signal']['direction']}")
    if 'execution_signal' in metadata:
        print(f"  Execution Score: {metadata['execution_signal']['score']:.3f}")
    print()

    # === Test 4: 포지션 사이징 테스트 ===
    print("[Test 4] Dynamic Position Sizing")
    print("-" * 80)

    test_cases = [
        (0.01, 0.9, "Low volatility, High confidence"),
        (0.05, 0.9, "High volatility, High confidence"),
        (0.01, 0.5, "Low volatility, Low confidence"),
        (0.05, 0.5, "High volatility, Low confidence"),
    ]

    for volatility, confidence, desc in test_cases:
        size = risk_manager.calculate_position_size(volatility, confidence)
        print(f"  {desc}:")
        print(f"    Vol={volatility:.1%}, Conf={confidence:.1f} → Size={size:,.0f} KRW")

    print()

    # === Test 5: TTL (Time-To-Live) 테스트 ===
    print("[Test 5] Signal TTL (Time-To-Live)")
    print("-" * 80)

    import time

    orderbook = create_mock_orderbook()
    signal, metadata = strategy.generate_signal(orderbook, 50_000_000, 100)

    if signal:
        print(f"  Initial TTL: {signal.remaining_ttl():.1f}s")
        print(f"  Is Valid: {signal.is_valid()}")

        # 5초 대기
        print("  Waiting 5 seconds...")
        time.sleep(5)

        print(f"  After 5s TTL: {signal.remaining_ttl():.1f}s")
        print(f"  Is Valid: {signal.is_valid()}")
    else:
        print("  No signal generated (데이터 부족 가능)")

    print()

    # === Test 6: Macro Filter 테스트 ===
    print("[Test 6] Macro Filter (Emergency Stop)")
    print("-" * 80)

    # 긴급 정지 활성화
    risk_manager.activate_emergency_stop("Test emergency stop")

    orderbook = create_mock_orderbook()
    signal, metadata = strategy.generate_signal(orderbook, 50_000_000, 100)

    print(f"  Emergency Stop Active: {risk_manager.emergency_stop}")
    print(f"  Signal Generated: {signal is not None}")
    print(f"  Macro Reason: {metadata['macro_signal']['reason']}")

    # 긴급 정지 해제
    risk_manager.deactivate_emergency_stop()

    print()

    # === Summary ===
    print("=" * 80)
    print("✅ All Tests Completed!")
    print("=" * 80)
    print()
    print("v0.9 Hierarchical Architecture:")
    print("  Level 1 (Macro): Risk management and market state filtering")
    print("  Level 2 (Strategic): RSI/MACD/BB pattern recognition")
    print("  Level 3 (Tactical): W-OBI microstructure execution timing")
    print()
    print("Key Features:")
    print("  ✓ TTL (Time-To-Live) signal expiration")
    print("  ✓ Dynamic position sizing (volatility + confidence)")
    print("  ✓ Signal caching for performance")
    print("  ✓ Hierarchical decision making")
    print()


if __name__ == "__main__":
    test_hierarchical_strategy()
