# HFT Bot v0.7 - Complete Production System

완전한 프로덕션 고빈도 거래 시스템

## 📁 파일 구조
```
hft_v07/
├── core.py           # 데이터 모델 & 설정
├── indicators.py     # 정확한 기술적 지표 (EMA/RSI/MACD)
├── strategy.py       # 가중치 기반 멀티 전략
├── risk.py          # 리스크 관리
├── ai_model.py      # AI 필터
├── backtester.py    # 완전한 백테스트 엔진
├── exchange.py      # 멀티 거래소 어댑터
├── position.py      # Thread-Safe 포지션 관리
├── telegram_bot.py  # 텔레그램 양방향 제어
├── dashboard.py     # 실시간 대시보드
├── bot.py           # 메인 봇
├── main.py          # CLI
└── requirements.txt # 의존성
```

## 🚀 빠른 시작

### 1. 설치
```bash
pip install -r requirements.txt
```

### 2. 환경변수 설정
```bash
export BITHUMB_API_KEY="your_key"
export BITHUMB_SECRET="your_secret"
export TELEGRAM_TOKEN="your_bot_token"  # 선택
export TELEGRAM_CHAT_ID="your_chat_id"  # 선택
```

### 3. 데이터 수집 (최소 3일)
```bash
python main.py collect --symbols BTC/KRW ETH/KRW
```

### 4. 백테스트
```bash
python main.py backtest --symbols BTC/KRW
```

### 5. AI 학습
```bash
python main.py train --symbols BTC/KRW --forward-ticks 20
```

### 6. 실전 봇 실행
```bash
python main.py bot \
  --symbols BTC/KRW ETH/KRW XRP/KRW \
  --amount 500000 \
  --max-positions 3 \
  --signal-threshold 0.6 \
  --telegram-token YOUR_TOKEN \
  --telegram-chat YOUR