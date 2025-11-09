"""
HFT Bot v0.7 - AI Model Module
MLP 기반 신호 필터링
"""

import os
import numpy as np
from typing import Tuple, Optional, Dict
import glob
import json
from datetime import datetime

try:
    from sklearn.neural_network import MLPClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    import joblib
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

from core import TradingConfig, OrderBook, Logger
from strategy import WeightedMultiStrategy


class AIModel:
    """AI 신호 필터"""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.model: Optional[MLPClassifier] = None
        self.scaler: Optional[StandardScaler] = None
        os.makedirs("models", exist_ok=True)
    
    def train_from_collected_data(
        self,
        symbol: str,
        forward_ticks: int = 20,
        logger: Optional[Logger] = None
    ) -> Dict[str, float]:
        """
        수집된 데이터로 학습
        
        Args:
            symbol: 심볼 (예: BTC/KRW)
            forward_ticks: 미래 몇 틱 후 수익률로 라벨 생성
            logger: 로거
        """
        if not ML_AVAILABLE:
            raise RuntimeError("sklearn not installed")
        
        if logger:
            logger.info(f"Training AI model for {symbol}...")
        
        # 데이터 파일 찾기
        pattern = os.path.join(
            self.config.backtest_data_dir,
            f"{symbol.replace('/', '_')}_*.jsonl"
        )
        files = glob.glob(pattern)
        
        if not files:
            raise FileNotFoundError(f"No data files for {symbol}")
        
        if logger:
            logger.info(f"Loading data from {files[0]}")
        
        # 데이터 로드
        orderbooks = []
        with open(files[0], 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    item = json.loads(line)
                    if item.get('type') == 'orderbook':
                        orderbooks.append(item['data'])
                except:
                    continue
        
        if logger:
            logger.info(f"Loaded {len(orderbooks)} orderbook snapshots")
        
        # 전략 엔진 초기화
        strategy = WeightedMultiStrategy(self.config)
        
        X_list = []
        y_list = []
        positive_samples = 0
        negative_samples = 0
        skipped_samples = 0
        
        # 피처 & 라벨 생성
        for i in range(len(orderbooks) - forward_ticks):
            ob = OrderBook(
                timestamp=datetime.now(),
                symbol=symbol,
                bids=orderbooks[i]['bids'][:10],
                asks=orderbooks[i]['asks'][:10]
            )
            
            price = orderbooks[i]['price']
            volume = orderbooks[i].get('volume', 0)
            
            # 신호 생성 (버퍼 채우기)
            _ = strategy.generate_signal(ob, price, volume)
            
            # 피처 추출
            features = strategy.extract_features(symbol)
            
            if features is None:
                continue
            
            # 라벨 생성: forward_ticks 후 수익률
            future_prices = [
                orderbooks[j]['price'] 
                for j in range(i+1, min(i+1+forward_ticks, len(orderbooks)))
            ]
            
            if not future_prices:
                continue
            
            entry_price = price
            max_gain = max((p - entry_price) / entry_price for p in future_prices)
            max_loss = min((p - entry_price) / entry_price for p in future_prices)
            
            # 라벨링: 익절 도달 → 1, 손절 도달 → 0, 중립 → 0
            if max_gain >= self.config.take_profit_rate:
                label = 1
                positive_samples += 1
            elif max_loss <= -self.config.stop_loss_rate:
                label = 0
                negative_samples += 1
            else:
                skipped_samples += 1
                continue
            
            X_list.append(features)
            y_list.append(label)
        
        X = np.array(X_list)
        y = np.array(y_list)
        
        if len(X) == 0 or len(y) == 0:
            raise RuntimeError("No labeled samples (all ticks skipped). Collect more data.")
        
        if logger:
            logger.info(f"Training samples: {len(X)}")
            logger.info(
                f"Positive samples: {positive_samples} "
                f"({positive_samples/len(y)*100:.1f}%) | "
                f"Negative samples: {negative_samples}"
            )
            if skipped_samples:
                logger.info(f"Skipped samples (no TP/SL): {skipped_samples}")
        
        # Train/Test Split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.3, random_state=42, stratify=y
        )
        
        # 스케일링
        self.scaler = StandardScaler()
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # MLP 학습
        self.model = MLPClassifier(
            hidden_layer_sizes=(128, 64, 32),
            activation='relu',
            solver='adam',
            max_iter=500,
            early_stopping=True,
            validation_fraction=0.1,
            n_iter_no_change=20,
            random_state=42,
            verbose=False
        )
        
        self.model.fit(X_train_scaled, y_train)
        
        # 평가
        train_acc = self.model.score(X_train_scaled, y_train)
        test_acc = self.model.score(X_test_scaled, y_test)
        
        if logger:
            logger.info(f"Train Accuracy: {train_acc:.3f}")
            logger.info(f"Test Accuracy: {test_acc:.3f}")
        
        # 저장
        joblib.dump({
            'model': self.model,
            'scaler': self.scaler,
            'symbol': symbol,
            'train_date': datetime.now().isoformat()
        }, self.config.ai_model_path)
        
        if logger:
            logger.info(f"Model saved to {self.config.ai_model_path}")
        
        return {
            'train_accuracy': train_acc,
            'test_accuracy': test_acc,
            'samples': len(X),
            'positive_rate': positive_samples / len(y),
            'label_distribution': {
                'positive': positive_samples,
                'negative': negative_samples,
                'skipped': skipped_samples
            }
        }
    
    def load(self) -> bool:
        """모델 로드"""
        if not ML_AVAILABLE:
            return False
        
        if not os.path.exists(self.config.ai_model_path):
            return False
        
        try:
            data = joblib.load(self.config.ai_model_path)
            self.model = data['model']
            self.scaler = data['scaler']
            return True
        except Exception as e:
            print(f"Model load failed: {e}")
            return False
    
    def predict(self, features: np.ndarray) -> Tuple[int, float]:
        """
        예측
        
        Returns:
            (prediction, confidence)
            prediction: 0 (거부) or 1 (통과)
            confidence: 0~1
        """
        if self.model is None or self.scaler is None:
            return 1, 1.0  # 모델 없으면 모두 통과
        
        try:
            features_scaled = self.scaler.transform([features])
            prediction = self.model.predict(features_scaled)[0]
            probabilities = self.model.predict_proba(features_scaled)[0]
            confidence = np.max(probabilities)
            
            return int(prediction), float(confidence)
        except Exception as e:
            print(f"Prediction error: {e}")
            return 1, 1.0
