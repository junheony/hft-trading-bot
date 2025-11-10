"""
HFT Bot v0.9 - 시드 1천만원 기준 설정
목표: 월 25억~60억 거래량
"""

from core import TradingConfig, ExchangeType

# ============================================================================
# 시드 1천만원 기준 공격적 설정
# ============================================================================

config_10m_aggressive = TradingConfig(
    # Exchange
    exchange_type=ExchangeType.BITHUMB,
    symbols=["BTC/KRW", "ETH/KRW", "XRP/KRW", "SOL/KRW"],  # 4개 심볼 병렬

    # Trading - 대폭 증가
    trade_amount_krw=3_500_000,      # 350만원
    max_positions=6,                  # 6개 (총 노출: 최대 2,100만원)
    max_position_size=6_000_000,      # 600만원 상한
    orderbook_depth=10,
    slippage_bps=2.5,                # 슬리피지 증가 (큰 주문)

    # Strategy Threshold - 더욱 완화
    signal_threshold=0.45,            # 0.6 → 0.45 (매우 공격적)

    # W-OBI - 대폭 완화
    wobi_window_size=80,              # 100 → 80 (더 빠른 반응)
    zscore_base_threshold=1.3,        # 2.0 → 1.3 (매우 자주 진입)

    # RSI - 범위 확대
    rsi_period=14,
    rsi_overbought=75,                # 70 → 75
    rsi_oversold=25,                  # 30 → 25

    # MACD (정확한 EMA)
    macd_fast=12,
    macd_slow=26,
    macd_signal=9,

    # Bollinger Bands
    bb_period=20,
    bb_std_dev=2.0,

    # Exit - 초고속 회전
    take_profit_rate=0.001,           # 0.15% → 0.10% (매우 빠른 익절)
    stop_loss_rate=0.0007,            # 0.10% → 0.07% (매우 빠른 손절)
    time_cut_seconds=40,              # 60초 → 40초 (초고속 타임컷)
    trailing_stop=True,               # 활성화 (수익 보호)
    trailing_stop_pct=0.0003,         # 0.05% → 0.03%

    # Fees
    maker_fee=0.0025,
    taker_fee=0.0025,

    # Risk - 강화
    max_daily_loss=-500_000,          # 시드의 5%
    max_consecutive_losses=3,         # 5 → 3 (더 보수적)

    # Dynamic
    enable_dynamic_params=True,
    volatility_window=100,
    dynamic_k=2.0,

    # Hierarchical Strategy (v0.9)
    use_hierarchical_strategy=True,

    # TTL - 초단축하여 매우 자주 재평가
    ttl_macro_seconds=30,             # 60s → 30s
    ttl_strategic_seconds=15,         # 30s → 15s
    ttl_tactical_seconds=3,           # 10s → 3s (극도로 짧게)

    # Dynamic Position Sizing
    enable_dynamic_sizing=True,
    min_position_factor=0.3,          # 0.2 → 0.3 (최소 90만원)
    max_position_factor=1.5,          # 최대 450만원
    target_volatility=0.02,

    # AI
    use_ai_filter=True,
    ai_confidence_threshold=0.55,     # 0.6 → 0.55 (완화)
    ai_model_path="models/mlp_model.pkl",

    # Backtest
    backtest_data_dir="data/collected",
    backtest_train_ratio=0.7,
)


# ============================================================================
# 시드 1천만원 기준 보수적 설정 (안정성 우선)
# ============================================================================

config_10m_conservative = TradingConfig(
    # Exchange
    exchange_type=ExchangeType.BITHUMB,
    symbols=["BTC/KRW", "ETH/KRW"],   # 2개 심볼

    # Trading - 중간 수준
    trade_amount_krw=2_500_000,       # 250만원
    max_positions=4,                   # 4개 (총 노출: 1,000만원)
    max_position_size=4_000_000,
    orderbook_depth=10,
    slippage_bps=1.8,

    # Strategy Threshold - 약간만 완화
    signal_threshold=0.55,             # 0.6 → 0.55

    # W-OBI
    wobi_window_size=100,
    zscore_base_threshold=1.8,         # 2.0 → 1.8 (약간 완화)

    # RSI
    rsi_period=14,
    rsi_overbought=72,
    rsi_oversold=28,

    # MACD
    macd_fast=12,
    macd_slow=26,
    macd_signal=9,

    # Bollinger Bands
    bb_period=20,
    bb_std_dev=2.0,

    # Exit - 기존 유지
    take_profit_rate=0.0015,           # 0.15%
    stop_loss_rate=0.001,              # 0.10%
    time_cut_seconds=50,               # 60초 → 50초
    trailing_stop=True,
    trailing_stop_pct=0.0005,

    # Fees
    maker_fee=0.0025,
    taker_fee=0.0025,

    # Risk - 매우 보수적
    max_daily_loss=-400_000,           # 시드의 4%
    max_consecutive_losses=4,

    # Dynamic
    enable_dynamic_params=True,
    volatility_window=100,
    dynamic_k=2.0,

    # Hierarchical Strategy
    use_hierarchical_strategy=True,

    # TTL - 기존보다 약간 단축
    ttl_macro_seconds=50,
    ttl_strategic_seconds=25,
    ttl_tactical_seconds=8,

    # Dynamic Position Sizing
    enable_dynamic_sizing=True,
    min_position_factor=0.25,
    max_position_factor=1.4,
    target_volatility=0.02,

    # AI
    use_ai_filter=True,
    ai_confidence_threshold=0.58,
    ai_model_path="models/mlp_model.pkl",

    # Backtest
    backtest_data_dir="data/collected",
    backtest_train_ratio=0.7,
)


# ============================================================================
# 사용 방법
# ============================================================================

def get_config_for_seed(seed_amount: int, risk_level: str = "conservative"):
    """
    시드 금액과 리스크 레벨에 따른 설정 반환

    Args:
        seed_amount: 시드 금액 (원)
        risk_level: "conservative" 또는 "aggressive"
    """
    if seed_amount >= 10_000_000:
        if risk_level == "aggressive":
            return config_10m_aggressive
        else:
            return config_10m_conservative
    else:
        # 기본 설정 (5백만원 기준)
        return TradingConfig()


if __name__ == "__main__":
    print("=" * 80)
    print("시드별 예상 거래량")
    print("=" * 80)
    print()

    configs = {
        "보수적 (250만원 포지션)": config_10m_conservative,
        "공격적 (300만원 포지션)": config_10m_aggressive,
    }

    for name, cfg in configs.items():
        print(f"[{name}]")
        print(f"  포지션 크기: {cfg.trade_amount_krw:,}원")
        print(f"  최대 포지션 수: {cfg.max_positions}개")
        print(f"  총 노출 한도: {cfg.trade_amount_krw * cfg.max_positions:,}원")
        print(f"  신호 임계값: {cfg.signal_threshold}")
        print(f"  타임컷: {cfg.time_cut_seconds}초")
        print()

        # 예상 거래량 계산 (빈도는 설정에 따라 다름)
        if name == "공격적 (300만원 포지션)":
            daily_trades_low = 60
            daily_trades_high = 120
        else:
            daily_trades_low = 40
            daily_trades_high = 70

        daily_volume_low = cfg.trade_amount_krw * daily_trades_low
        daily_volume_high = cfg.trade_amount_krw * daily_trades_high

        monthly_low = daily_volume_low * 20
        monthly_high = daily_volume_high * 20

        print(f"  예상 일 거래:")
        print(f"    최소: {daily_volume_low:,}원 ({daily_trades_low}회)")
        print(f"    최대: {daily_volume_high:,}원 ({daily_trades_high}회)")
        print()
        print(f"  예상 월 거래량:")
        print(f"    최소: {monthly_low/100000000:.1f}억원")
        print(f"    최대: {monthly_high/100000000:.1f}억원")
        print()
        print(f"  일일 손실 한도: {cfg.max_daily_loss:,}원 (시드의 {abs(cfg.max_daily_loss)/10000000*100:.0f}%)")
        print()
        print("-" * 80)
        print()
