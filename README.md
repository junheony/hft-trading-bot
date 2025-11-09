# HFT Bot v0.9 - Hierarchical Agent Architecture

완전한 프로덕션 고빈도 거래 시스템 (계층적 에이전트 + 동적 포지션 사이징)

## 주요 개선사항 (v0.9) 🚀

### 1. **계층적 의사결정 구조** (핵심 개선)

```
Level 1 (Macro Filter)  → 거시적 시장 상태 필터링 (리스크 관리)
    ↓
Level 2 (Strategic)     → 기술적 지표 기반 방향성 결정 (RSI/MACD/BB)
    ↓
Level 3 (Tactical)      → 오더북 미시구조 기반 실행 타이밍 (W-OBI)
```

**기존 v0.8의 문제점**:
- 모든 신호(W-OBI, RSI, MACD)를 단순 가중 평균
- 미시구조(W-OBI)와 중기 추세(MACD)를 같은 레벨에서 혼합
- 시장 상태 필터링 부재

**v0.9 해결 방안**:
- W-OBI를 "Execution Agent"로 전문화 (실행 타이밍만 담당)
- RSI/MACD/BB를 "Strategy Agent"로 분리 (방향성 결정)
- Macro Filter로 리스크 관리 우선 체크

**실제 동작 예시**:
```python
# Level 1: Macro Filter
if risk_manager.emergency_stop or daily_loss_limit_reached:
    return NO_SIGNAL  # 진입 차단

# Level 2: Strategic Signal (RSI/MACD/BB)
strategic_score = analyze_indicators()
if strategic_score < 0.6:
    return NO_SIGNAL  # 방향성 불명확

# Level 3: Tactical Execution (W-OBI)
if orderbook_imbalance_favorable and spread_tight:
    return EXECUTE_NOW  # 최적 타이밍
```

### 2. **TTL (Time-To-Live) 신호 유효기간**

```python
signal = Signal(
    direction=SignalDirection.LONG,
    score=0.85,
    ttl_seconds=30,  # 30초간만 유효
    timestamp=datetime.now()
)

# 신호 만료 확인
if signal.is_valid():  # False if expired
    execute_trade()
```

- 급격한 시장 변화 시 오래된 신호 자동 무효화
- Macro: 60초, Strategic: 30초, Tactical: 10초
- 신호 캐싱으로 성능 최적화

### 3. **동적 포지션 사이징**

```python
position_size = risk_manager.calculate_position_size(
    volatility=0.03,   # 현재 변동성
    confidence=0.85    # 신호 신뢰도
)
# → 변동성 높으면 포지션 축소 (리스크 감소)
# → 신호 약하면 포지션 축소 (확신 부족)
# → Sharpe Ratio 좋으면 포지션 증가 (성과 좋음)
# → 연속 손실 시 포지션 축소 (방어적)
```

**조정 요소**:
| 요소 | 효과 | 예시 |
|------|------|------|
| 변동성 | 높을수록 축소 | 3% 변동성 → 67% 크기 |
| 신뢰도 | 낮을수록 축소 | 0.5 신뢰도 → 50% 크기 |
| Sharpe Ratio | 좋을수록 증가 | 1.5 Sharpe → 120% 크기 |
| 연속 손실 | 많을수록 축소 | 3연패 → 50% 크기 |

**최종 포지션 크기** = Base × Volatility × Confidence × Sharpe × Consecutive

### 4. **W-OBI 전문화 (Execution Agent)**

- **기존**: 35% 가중치로 다른 지표와 평등하게 혼합
- **v0.9**: 오더북 미시구조만 분석하는 Execution Agent로 독립
- **역할**: "지금이 체결하기 좋은 타이밍인가?"만 판단
- **체크 항목**:
  - W-OBI Z-Score > 2.0 (충분한 호가 불균형)
  - 스프레드 < 0.1% (슬리피지 적음)
  - 깊이 비율 유리 (충분한 유동성)

---

## 파일 구조 (v0.9)

```
hft_v09/
├── core.py                    # 데이터 모델 & 설정
├── indicators.py              # 정확한 기술적 지표 (EMA/RSI/MACD)
├── signal.py                  # TTL 지원 신호 클래스 ✨ 신규
├── agents.py                  # 계층적 에이전트 (Macro/Strategic/Tactical) ✨ 신규
├── hierarchical_strategy.py   # 계층적 전략 시스템 ✨ 신규
├── strategy.py                # 기존 가중치 기반 전략 (호환성)
├── risk.py                    # 리스크 관리 + 동적 포지션 사이징 ✨ 개선
├── ai_model.py                # AI 필터
├── backtester.py              # 완전한 백테스트 엔진
├── exchange.py                # 멀티 거래소 어댑터
├── position.py                # Thread-Safe 포지션 관리
├── telegram_bot.py            # 텔레그램 양방향 제어
├── dashboard.py               # 실시간 대시보드
├── bot.py                     # 메인 봇
├── main.py                    # CLI
├── test_indicators.py         # 지표 정확성 테스트
├── test_hierarchical.py       # 계층적 시스템 테스트 ✨ 신규
└── requirements.txt           # 의존성
```

---

## 빠른 시작

### 1. 설치

```bash
# 가상환경 생성 (권장)
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

### 2. 계층적 시스템 테스트

```bash
python test_hierarchical.py
```

**테스트 내용**:
- Level 1~3 에이전트 초기화
- TTL (Time-To-Live) 신호 만료
- 동적 포지션 사이징
- Macro Filter (긴급 정지)

### 3. 데이터 수집

```bash
python main.py collect --symbols BTC/KRW ETH/KRW
```

### 4. 백테스트 (계층적 전략)

```bash
python main.py backtest --symbols BTC/KRW --hierarchical
```

### 5. 실전 봇 실행 (v0.9 계층적 모드)

```bash
python main.py bot \
  --symbols BTC/KRW ETH/KRW \
  --amount 500000 \
  --hierarchical \
  --signal-threshold 0.6
```

---

## v0.9 vs v0.8 비교

| 항목 | v0.8 | v0.9 |
|------|------|------|
| **의사결정 구조** | 단일 레벨 (모든 지표 가중 평균) | 3단계 계층 (Macro → Strategic → Tactical) |
| **W-OBI 역할** | 35% 가중치 | Execution Agent (실행 타이밍 전문) |
| **포지션 사이징** | 고정 금액 | 동적 조절 (변동성/신뢰도/성과) |
| **신호 유효기간** | 없음 | TTL (10~60초) |
| **리스크 필터** | 진입 후 체크 | 진입 전 우선 체크 (Macro Filter) |
| **신호 캐싱** | 없음 | TTL 기반 캐싱 (성능 최적화) |

---

## 이전 개선사항 (v0.8)

### 1. 기술적 지표 정확도 수정
- **MACD 계산 오류 수정**: 표준 EMA 기반 MACD (TradingView/HTS 호환)
- **RSI 검증**: Wilder's smoothing 방식으로 정확하게 구현됨

### 2. 완전한 백테스팅 엔진
- JSONL 데이터 재생
- 슬리피지 + 수수료 반영
- CSV 결과 저장

### 3. AI 모델 라벨링 개선
- TP/SL 도달 샘플만 학습
- 라벨 분포 추적

### 4. 실시간 Sharpe Ratio
- 리스크 관리 통합
- 대시보드 표시

---

## 검증 프로세스

### 1단계: 계층적 시스템 테스트
```bash
python test_hierarchical.py
```
- 각 에이전트 독립 동작 확인
- TTL 만료 테스트
- 동적 포지션 사이징 검증

### 2단계: 지표 정확성 검증
```bash
python test_indicators.py
```
- MACD Signal Line 정확도
- RSI Wilder's smoothing

### 3단계: 백테스트
```bash
python main.py backtest --symbols BTC/KRW --hierarchical
```
- Sharpe Ratio > 1.0 목표
- Win Rate > 50% 목표
- Max Drawdown 모니터링

### 4단계: 페이퍼 트레이딩
```bash
python main.py bot --amount 10000 --symbols BTC/KRW --hierarchical
```

---

## 전략 철학 (v0.9)

### 계층적 분리의 원칙

1. **Macro (거시)**: "지금 거래해도 되는가?" (리스크 관리)
   - 일일 손실 한도
   - 연속 손실 체크
   - Sharpe Ratio 추세

2. **Strategic (전략)**: "어느 방향으로 거래할 것인가?" (중기 패턴)
   - RSI, MACD, Bollinger Bands
   - 30초 TTL

3. **Tactical (전술)**: "지금이 최적의 실행 시점인가?" (미시구조)
   - W-OBI 호가 불균형
   - 스프레드, 깊이
   - 10초 TTL

### 동적 적응의 원칙

- **변동성 높음** → 포지션 축소 (방어)
- **신호 약함** → 포지션 축소 (신중)
- **성과 좋음** → 포지션 증가 (공격)
- **연속 손실** → 포지션 축소 (회복 대기)

---

## 주의사항

- 이 봇은 교육 및 연구 목적입니다
- 실전 운영 시 손실 가능성이 있으므로 충분히 테스트하세요
- API 키는 절대 공개 저장소에 올리지 마세요
- 백테스트 결과가 미래 성과를 보장하지 않습니다
- v0.9는 v0.8보다 보수적으로 진입합니다 (3단계 필터)

---

## 라이선스

MIT License

## 기여

이슈와 PR은 환영합니다!

---

**HFT Bot v0.9** - Hierarchical Agents + Dynamic Position Sizing
