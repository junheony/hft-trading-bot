# HFT Bot v0.8 - Complete Production System

완전한 프로덕션 고빈도 거래 시스템 (정확한 지표 + 백테스팅 엔진)

## 주요 개선사항 (v0.8)

### 1. 기술적 지표 정확도 수정
- **MACD 계산 오류 수정**: 이제 표준 EMA 기반 MACD를 정확하게 계산합니다
  - MACD Line = EMA(12) - EMA(26)
  - Signal Line = EMA(MACD Line, 9)
  - TradingView/HTS와 동일한 값 산출
- **RSI 검증**: Wilder's smoothing 방식으로 정확하게 구현됨 (검증 완료)
- **테스트 스크립트 추가**: `test_indicators.py`로 지표 정확성 검증 가능

### 2. 완전한 백테스팅 엔진
- **JSONL 데이터 재생**: 수집된 실제 데이터로 과거 검증
- **정확한 체결 모델**: 슬리피지 (1.5 bps) + 수수료 (0.25%) 반영
- **완전한 TP/SL 로직**: Take Profit (0.15%) / Stop Loss (0.1%) / Time Cut (60s) / Trailing Stop
- **CSV 결과 저장**: `backtest/` 디렉터리에 거래 내역 자동 저장
- **성과 지표**: Win Rate, Sharpe Ratio, Max Drawdown, Profit Factor 등

### 3. AI 모델 라벨링 개선
- **TP/SL 도달 샘플만 학습**: 중립 샘플 제외로 데이터 품질 향상
- **라벨 분포 추적**: 학습 데이터 편향 모니터링
- **스킵 샘플 로깅**: 얼마나 많은 샘플이 제외되었는지 확인 가능

### 4. 실시간 Sharpe Ratio
- **리스크 관리**: 실시간 Sharpe Ratio 계산 (연율화)
- **대시보드 표시**: 웹 대시보드에서 Sharpe Ratio 실시간 모니터링

## 파일 구조

```
hft_v08/
├── core.py              # 데이터 모델 & 설정 (slippage 추가)
├── indicators.py        # 정확한 기술적 지표 (EMA/RSI/MACD) ✨ 수정
├── strategy.py          # 가중치 기반 멀티 전략
├── risk.py              # 리스크 관리 (Sharpe Ratio) ✨ 개선
├── ai_model.py          # AI 필터 (라벨링 개선) ✨ 개선
├── backtester.py        # 완전한 백테스트 엔진 ✨ v0.8
├── exchange.py          # 멀티 거래소 어댑터
├── position.py          # Thread-Safe 포지션 관리
├── telegram_bot.py      # 텔레그램 양방향 제어
├── dashboard.py         # 실시간 대시보드 (Sharpe 표시) ✨ 개선
├── bot.py               # 메인 봇
├── main.py              # CLI (백테스트 CSV 저장) ✨ 개선
├── test_indicators.py   # 지표 정확성 테스트 ✨ 신규
└── requirements.txt     # 의존성
```

## 빠른 시작

### 1. 설치

```bash
# 가상환경 생성 (권장)
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

### 2. 환경변수 설정

```bash
export BITHUMB_API_KEY="your_key"
export BITHUMB_SECRET="your_secret"
export TELEGRAM_TOKEN="your_bot_token"  # 선택
export TELEGRAM_CHAT_ID="your_chat_id"  # 선택
```

### 3. 데이터 수집 (최소 3일 권장)

```bash
python main.py collect --symbols BTC/KRW ETH/KRW
```

데이터는 `data/` 디렉터리에 JSONL 형식으로 저장됩니다.

### 4. 지표 정확성 테스트 (선택)

```bash
python test_indicators.py
```

RSI, MACD, EMA 계산이 정확한지 검증합니다.

### 5. 백테스트 실행

```bash
python main.py backtest --symbols BTC/KRW
```

결과는 `backtest/backtest_BTC_KRW.csv`에 저장됩니다.

**주요 출력 지표**:
- Total Trades: 거래 횟수
- Win Rate: 승률 (%)
- Total PnL: 총 손익 (KRW)
- Sharpe Ratio: 위험 대비 수익률
- Max Drawdown: 최대 낙폭 (KRW, %)
- Profit Factor: 총 수익 / 총 손실
- Average Holding Time: 평균 보유 시간 (초)

### 6. AI 모델 학습

```bash
python main.py train --symbols BTC/KRW --forward-ticks 20
```

**주의사항**:
- 백테스트에서 긍정적인 결과가 나온 후 학습하세요
- TP/SL 도달 샘플만 사용하므로 충분한 데이터가 필요합니다
- 라벨 분포를 확인하여 데이터 편향이 없는지 검토하세요

### 7. 실전 봇 실행

```bash
python main.py bot \
  --symbols BTC/KRW ETH/KRW XRP/KRW \
  --amount 500000 \
  --max-positions 3 \
  --signal-threshold 0.6 \
  --telegram-token YOUR_TOKEN \
  --telegram-chat YOUR_ID
```

### 8. 대시보드 확인

브라우저에서 `http://localhost:8080` 접속

대시보드에서 확인 가능한 정보:
- 일일 손익 (Daily PnL)
- 승률 (Win Rate)
- Sharpe Ratio ✨ 신규
- 활성 포지션 실시간 모니터링

## 전략 구성

### 가중치 기반 앙상블 전략

```python
# core.py의 TradingConfig에서 조정 가능
weight_wobi: float = 0.35      # W-OBI (호가 불균형)
weight_rsi: float = 0.25       # RSI
weight_macd: float = 0.20      # MACD ✨ 정확한 계산
weight_bb: float = 0.10        # Bollinger Bands
weight_stoch: float = 0.10     # Stochastic
signal_threshold: float = 0.6  # 진입 신호 임계값
```

### 리스크 관리 파라미터

```python
take_profit_rate: float = 0.0015   # 0.15% 익절
stop_loss_rate: float = 0.001      # 0.1% 손절
time_cut_seconds: int = 60         # 60초 타임컷
trailing_stop: bool = False        # 트레일링 스톱 (선택)
trailing_stop_pct: float = 0.0005  # 0.05% 트레일링
```

**백테스트로 파라미터를 최적화한 후 실전에 적용하세요!**

## 검증 프로세스

### 1단계: 지표 정확성 검증
```bash
python test_indicators.py
```
- EMA, RSI, MACD가 정확하게 계산되는지 확인
- TradingView 값과 비교 (±1% 이내 오차)

### 2단계: 백테스트 검증
```bash
python main.py backtest --symbols BTC/KRW
```
- 과거 데이터로 전략 성과 확인
- Sharpe Ratio > 1.0, Win Rate > 50% 목표
- Max Drawdown을 확인하여 위험 평가

### 3단계: AI 모델 검증
```bash
python main.py train --symbols BTC/KRW --forward-ticks 20
```
- Test Accuracy > 60% 목표
- 라벨 분포가 심하게 편향되지 않았는지 확인
- Positive Rate가 너무 낮으면 데이터 수집 기간 연장

### 4단계: 페이퍼 트레이딩
```bash
# 소액으로 먼저 테스트
python main.py bot --amount 10000 --symbols BTC/KRW
```

### 5단계: 실전 운영
- 충분한 검증 후 금액 증액
- 대시보드와 텔레그램으로 실시간 모니터링
- 일일 손실 한도 설정 확인

## 주의사항

- 이 봇은 교육 및 연구 목적입니다
- 실전 운영 시 손실 가능성이 있으므로 충분히 테스트하세요
- API 키는 절대 공개 저장소에 올리지 마세요
- 백테스트 결과가 미래 성과를 보장하지 않습니다
- 슬리피지와 수수료를 고려한 현실적인 기대치를 설정하세요

## 라이선스

MIT License

## 기여

이슈와 PR은 환영합니다!

---

**HFT Bot v0.8** - Accurate Indicators + Complete Backtesting Engine
