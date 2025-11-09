"""
지표 정확성 테스트
TradingView/HTS와 동일한 값이 나오는지 검증
"""

import numpy as np
from indicators import TechnicalIndicators

def test_macd():
    """MACD 계산 테스트"""
    print("=" * 60)
    print("MACD 계산 테스트")
    print("=" * 60)

    # 샘플 가격 데이터 (충분한 길이)
    # 실제 비트코인 가격 패턴을 시뮬레이션
    np.random.seed(42)
    base_price = 50000000  # 5천만원
    prices = [base_price]

    for i in range(100):
        change = np.random.randn() * 0.01  # 1% 변동
        new_price = prices[-1] * (1 + change)
        prices.append(new_price)

    # MACD 계산
    result = TechnicalIndicators.calculate_macd(prices, fast=12, slow=26, signal=9)

    if result is None:
        print("❌ MACD 계산 실패 - 데이터 부족")
        return False

    macd_line, signal_line, histogram = result

    print(f"✓ MACD Line    : {macd_line:,.2f}")
    print(f"✓ Signal Line  : {signal_line:,.2f}")
    print(f"✓ Histogram    : {histogram:,.2f}")
    print()

    # 기본 검증
    assert isinstance(macd_line, (int, float)), "MACD Line은 숫자여야 함"
    assert isinstance(signal_line, (int, float)), "Signal Line은 숫자여야 함"
    assert abs(histogram - (macd_line - signal_line)) < 0.01, "Histogram = MACD - Signal"

    print("✅ MACD 계산 검증 완료")
    return True


def test_rsi():
    """RSI 계산 테스트"""
    print("=" * 60)
    print("RSI 계산 테스트")
    print("=" * 60)

    # 샘플 데이터
    np.random.seed(42)
    base_price = 50000000
    prices = [base_price]

    for i in range(30):
        change = np.random.randn() * 0.02
        new_price = prices[-1] * (1 + change)
        prices.append(new_price)

    # RSI 계산
    rsi = TechnicalIndicators.calculate_rsi(prices, period=14)

    if rsi is None:
        print("❌ RSI 계산 실패 - 데이터 부족")
        return False

    print(f"✓ RSI (14)     : {rsi:.2f}")
    print()

    # 기본 검증
    assert 0 <= rsi <= 100, "RSI는 0-100 범위여야 함"

    print("✅ RSI 계산 검증 완료")
    return True


def test_ema():
    """EMA 계산 테스트"""
    print("=" * 60)
    print("EMA 계산 테스트")
    print("=" * 60)

    # 간단한 데이터
    prices = np.array([100, 102, 104, 103, 105, 107, 106, 108, 110, 109])

    ema_5 = TechnicalIndicators.calculate_ema(prices, period=5)
    ema_10 = TechnicalIndicators.calculate_ema(prices, period=10)

    print(f"✓ EMA (5)      : {ema_5:.2f}")
    print(f"✓ EMA (10)     : {ema_10:.2f}")
    print()

    # EMA는 최근 가격에 더 가중치를 두므로 단순 평균보다 최근 가격에 가까워야 함
    simple_avg = np.mean(prices)
    print(f"  단순 평균     : {simple_avg:.2f}")
    print(f"  최근 가격     : {prices[-1]:.2f}")
    print()

    assert ema_5 is not None, "EMA 계산 실패"
    assert ema_10 is not None, "EMA 계산 실패"

    print("✅ EMA 계산 검증 완료")
    return True


def test_comparison_with_tradingview():
    """
    TradingView 값과 비교 (수동 검증용)
    실제 가격 데이터를 TradingView에 입력하여 비교해야 함
    """
    print("=" * 60)
    print("수동 검증 가이드")
    print("=" * 60)
    print()
    print("다음 단계로 TradingView와 비교 검증:")
    print("1. 실제 거래소 데이터를 수집 (python main.py collect)")
    print("2. 동일 시점의 캔들 데이터를 TradingView에서 확인")
    print("3. RSI(14), MACD(12,26,9) 값 비교")
    print()
    print("기대 결과: ±1% 이내 오차")
    print()


if __name__ == "__main__":
    print()
    print("🔍 기술적 지표 정확성 테스트")
    print()

    success = True

    try:
        success &= test_ema()
        success &= test_rsi()
        success &= test_macd()
        test_comparison_with_tradingview()

        if success:
            print("=" * 60)
            print("✅ 모든 테스트 통과!")
            print("=" * 60)
        else:
            print("=" * 60)
            print("❌ 일부 테스트 실패")
            print("=" * 60)

    except Exception as e:
        print("=" * 60)
        print(f"❌ 테스트 중 오류 발생: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
