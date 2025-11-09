"""
HFT Bot v0.7 - Exchange Module
멀티 거래소 지원
"""

import asyncio
from typing import Tuple, Optional

try:
    import ccxt.async_support as ccxt
    CCXT_AVAILABLE = True
except ImportError:
    CCXT_AVAILABLE = False

from core import TradingConfig, ExchangeType, OrderBook


class ExchangeAdapter:
    """멀티 거래소 어댑터"""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.exchange = None
        self.exchange_type = config.exchange_type
    
    async def initialize(self) -> bool:
        """거래소 초기화"""
        if not CCXT_AVAILABLE:
            print("Error: ccxt not installed")
            return False
        
        # API 키 환경변수
        import os
        key_name = f"{self.exchange_type.value.upper()}_API_KEY"
        secret_name = f"{self.exchange_type.value.upper()}_SECRET"
        
        api_key = os.getenv(key_name)
        api_secret = os.getenv(secret_name)
        
        if not api_key or not api_secret:
            print(f"Error: {key_name} and {secret_name} required")
            return False
        
        # 거래소 인스턴스 생성
        exchange_class = getattr(ccxt, self.exchange_type.value)
        self.exchange = exchange_class({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot'
            }
        })
        
        try:
            await self.exchange.load_markets()
            print(f"✅ {self.exchange_type.value} connected")
            return True
        except Exception as e:
            print(f"❌ {self.exchange_type.value} connection failed: {e}")
            return False
    
    async def fetch_orderbook(self, symbol: str) -> OrderBook:
        """오더북 조회"""
        from datetime import datetime
        
        ob = await self.exchange.watch_order_book(symbol)
        
        return OrderBook(
            timestamp=datetime.now(),
            symbol=symbol,
            bids=ob['bids'][:20],
            asks=ob['asks'][:20]
        )
    
    async def fetch_ticker(self, symbol: str) -> dict:
        """티커 조회"""
        return await self.exchange.watch_ticker(symbol)
    
    async def create_market_buy_with_retry(
        self,
        symbol: str,
        krw_amount: float,
        max_retries: int = 3
    ) -> Tuple[float, float, float]:
        """
        재시도 로직 포함 시장가 매수
        
        Returns:
            (avg_price, filled_amount, fee)
        """
        for attempt in range(max_retries):
            try:
                return await self._create_market_buy(symbol, krw_amount)
            except Exception as e:
                print(f"Buy attempt {attempt+1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(self.config.entry_retry_delay * (2 ** attempt))
                else:
                    raise
    
    async def _create_market_buy(
        self,
        symbol: str,
        krw_amount: float
    ) -> Tuple[float, float, float]:
        """시장가 매수 (내부)"""
        ticker = await self.exchange.fetch_ticker(symbol)
        amount = krw_amount / ticker['last']
        
        order = await self.exchange.create_market_buy_order(symbol, amount)
        
        # 체결 대기
        for _ in range(10):
            if order.get('status') == 'closed':
                break
            await asyncio.sleep(0.5)
            order = await self.exchange.fetch_order(order['id'], symbol)
        
        if order.get('status') != 'closed':
            raise TimeoutError("Order not filled")
        
        # 실제 체결 정보
        filled = order.get('filled', 0)
        cost = order.get('cost', 0)
        
        # 평균 체결가
        if filled > 0:
            avg_price = cost / filled
        else:
            avg_price = order.get('average', order.get('price', 0))
        
        # 수수료 (거래소 응답에서 추출 시도)
        fee_info = order.get('fee', {})
        if fee_info and 'cost' in fee_info:
            fee = fee_info['cost']
        else:
            # Fallback: 추정
            fee = cost * self.config.taker_fee
        
        return avg_price, filled, fee
    
    async def create_market_sell_with_retry(
        self,
        symbol: str,
        amount: float,
        max_retries: int = 5
    ) -> Tuple[float, float]:
        """
        재시도 로직 포함 시장가 매도
        
        Returns:
            (avg_price, fee)
        """
        for attempt in range(max_retries):
            try:
                return await self._create_market_sell(symbol, amount)
            except Exception as e:
                print(f"Sell attempt {attempt+1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(self.config.exit_retry_delay * (2 ** attempt))
                else:
                    raise
    
    async def _create_market_sell(
        self,
        symbol: str,
        amount: float
    ) -> Tuple[float, float]:
        """시장가 매도 (내부)"""
        order = await self.exchange.create_market_sell_order(symbol, amount)
        
        for _ in range(10):
            if order.get('status') == 'closed':
                break
            await asyncio.sleep(0.5)
            order = await self.exchange.fetch_order(order['id'], symbol)
        
        if order.get('status') != 'closed':
            raise TimeoutError("Order not filled")
        
        cost = order.get('cost', 0)
        filled = order.get('filled', 0)
        
        if filled > 0:
            avg_price = cost / filled
        else:
            avg_price = order.get('average', order.get('price', 0))
        
        fee_info = order.get('fee', {})
        if fee_info and 'cost' in fee_info:
            fee = fee_info['cost']
        else:
            fee = cost * self.config.taker_fee
        
        return avg_price, fee
    
    async def close(self):
        """연결 종료"""
        if self.exchange:
            await self.exchange.close()