"""
HFT Bot v0.7 - Main Entry Point
CLI 인터페이스
"""

import os
import sys
import asyncio
import argparse
import threading

from core import TradingConfig, Logger, ExchangeType
from strategy import WeightedMultiStrategy
from risk import RiskManager
from ai_model import AIModel
from backtester import Backtester
from exchange import ExchangeAdapter
from position import PositionManager
from telegram_bot import TelegramBot
from bot import HFTBot
from dashboard import run_dashboard


def print_banner():
    """배너 출력"""
    banner = """
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║          HFT Bot v0.7 - Complete System                  ║
    ║          Production-Ready Quantitative Trading           ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """
    print(banner)


async def mode_bot(args, config: TradingConfig):
    """봇 모드"""
    logger = Logger("hft_bot")
    
    logger.info("Initializing components...")
    
    # Exchange
    exchange = ExchangeAdapter(config)
    if not await exchange.initialize():
        logger.error("Exchange initialization failed")
        return
    
    # Strategy
    strategy = WeightedMultiStrategy(config)
    
    # Risk
    risk = RiskManager(config)
    
    # Position
    pm = PositionManager(config)
    
    # AI
    ai = None
    if config.use_ai_filter:
        ai = AIModel(config)
        if ai.load():
            logger.info("AI model loaded")
        else:
            logger.warning("AI model not found, running without AI filter")
            config.use_ai_filter = False
    
    # Telegram
    telegram = None
    if config.telegram_token and config.telegram_chat_id:
        telegram = TelegramBot(config, logger)
        telegram.setup_handlers()
        
        # 텔레그램 폴링 시작 (백그라운드)
        asyncio.create_task(telegram.run_polling())
    
    # Bot
    bot = HFTBot(
        config=config,
        logger=logger,
        exchange=exchange,
        strategy=strategy,
        position_manager=pm,
        risk_manager=risk,
        ai_model=ai,
        telegram=telegram
    )
    
    # Dashboard (별도 스레드)
    if not args.no_dashboard:
        dashboard_thread = threading.Thread(
            target=run_dashboard,
            args=(bot.dashboard_state,),
            daemon=True
        )
        dashboard_thread.start()
        logger.info("📊 Dashboard: http://localhost:8000")
    
    # 봇 실행
    try:
        await bot.run()
    finally:
        await exchange.close()


async def mode_backtest(args, config: TradingConfig):
    """백테스트 모드"""
    logger = Logger("backtest")
    
    backtester = Backtester(config, logger)
    
    for symbol in config.symbols:
        logger.info(f"\nBacktesting {symbol}...")
        try:
            stats = backtester.run(symbol, use_test_data=True)
            
            # CSV 저장
            import csv
            with open(f"backtest/backtest_{symbol.replace('/', '_')}.csv", 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=stats['trades'][0].keys() if stats.get('trades') else [])
                if stats.get('trades'):
                    writer.writeheader()
                    writer.writerows(stats['trades'])
            
            logger.info(f"Results saved to backtest/backtest_{symbol.replace('/', '_')}.csv")
            
        except Exception as e:
            logger.error(f"Backtest failed for {symbol}: {e}")


async def mode_train_ai(args, config: TradingConfig):
    """AI 학습 모드"""
    logger = Logger("ai_trainer")
    
    ai = AIModel(config)
    
    for symbol in config.symbols:
        logger.info(f"\nTraining AI for {symbol}...")
        try:
            metrics = ai.train_from_collected_data(
                symbol=symbol,
                forward_ticks=args.forward_ticks,
                logger=logger
            )
            
            logger.info(f"Training completed: {metrics}")
            
        except Exception as e:
            logger.error(f"Training failed for {symbol}: {e}")


async def mode_collect(args, config: TradingConfig):
    """데이터 수집 모드"""
    logger = Logger("collector")
    
    # 간단한 데이터 수집기
    try:
        import ccxt.async_support as ccxt
    except ImportError:
        logger.error("ccxt not installed")
        return
    
    exchange = ccxt.bithumb({'enableRateLimit': True})
    await exchange.load_markets()
    
    logger.info(f"Starting data collection for {len(config.symbols)} symbols")
    logger.info("Press Ctrl+C to stop")
    
    import json
    from datetime import datetime
    
    os.makedirs("data/collected", exist_ok=True)
    
    files = {}
    for symbol in config.symbols:
        filename = f"data/collected/{symbol.replace('/', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
        files[symbol] = open(filename, 'a', encoding='utf-8')
    
    tick_counts = {s: 0 for s in config.symbols}
    
    try:
        while True:
            for symbol in config.symbols:
                try:
                    ob = await exchange.watch_order_book(symbol)
                    ticker = await exchange.watch_ticker(symbol)
                    
                    if not ob.get('bids') or not ob.get('asks'):
                        continue
                    
                    data = {
                        'timestamp': datetime.now().isoformat(),
                        'type': 'orderbook',
                        'symbol': symbol,
                        'data': {
                            'bids': ob['bids'][:20],
                            'asks': ob['asks'][:20],
                            'price': ticker['last'],
                            'volume': ticker.get('quoteVolume', 0)
                        }
                    }
                    
                    files[symbol].write(json.dumps(data, ensure_ascii=False) + '\n')
                    files[symbol].flush()
                    
                    tick_counts[symbol] += 1
                    
                    if tick_counts[symbol] % 100 == 0:
                        logger.info(f"{symbol}: {tick_counts[symbol]} ticks collected")
                
                except Exception as e:
                    logger.error(f"Collection error [{symbol}]: {e}")
            
            await asyncio.sleep(0.05)
    
    except KeyboardInterrupt:
        logger.info("\nStopping collection...")
    finally:
        for f in files.values():
            f.close()
        await exchange.close()
        
        total = sum(tick_counts.values())
        logger.info(f"Total ticks collected: {total}")


def main():
    """메인 진입점"""
    print_banner()
    
    parser = argparse.ArgumentParser(description='HFT Bot v0.7')
    
    parser.add_argument(
        'mode',
        choices=['bot', 'backtest', 'train', 'collect'],
        help='Operating mode'
    )
    
    # Exchange
    parser.add_argument('--exchange', type=str, default='bithumb',
                       choices=['bithumb', 'upbit', 'coinone'],
                       help='Exchange')
    
    # Symbols
    parser.add_argument('--symbols', nargs='+', default=['BTC/KRW'],
                       help='Trading symbols')
    
    # Trading
    parser.add_argument('--amount', type=float, default=500_000,
                       help='Trade amount (KRW)')
    parser.add_argument('--max-positions', type=int, default=3,
                       help='Max simultaneous positions')
    
    # Strategy
    parser.add_argument('--signal-threshold', type=float, default=0.6,
                       help='Signal score threshold (0~1)')
    parser.add_argument('--no-dynamic', action='store_true',
                       help='Disable dynamic parameters')
    
    # AI
    parser.add_argument('--no-ai', action='store_true',
                       help='Disable AI filter')
    parser.add_argument('--forward-ticks', type=int, default=20,
                       help='Forward ticks for AI training')
    
    # Telegram
    parser.add_argument('--telegram-token', type=str,
                       help='Telegram bot token')
    parser.add_argument('--telegram-chat', type=str,
                       help='Telegram chat ID')
    
    # Dashboard
    parser.add_argument('--no-dashboard', action='store_true',
                       help='Disable dashboard')
    
    args = parser.parse_args()
    
    # Config 생성
    config = TradingConfig(
        exchange_type=ExchangeType(args.exchange),
        symbols=args.symbols,
        trade_amount_krw=args.amount,
        max_positions=args.max_positions,
        signal_threshold=args.signal_threshold,
        enable_dynamic_params=not args.no_dynamic,
        use_ai_filter=not args.no_ai,
        telegram_token=args.telegram_token or os.getenv('TELEGRAM_TOKEN'),
        telegram_chat_id=args.telegram_chat or os.getenv('TELEGRAM_CHAT_ID')
    )
    
    print("\n" + "="*60)
    print(f"Mode: {args.mode.upper()}")
    print(f"Exchange: {config.exchange_type.value}")
    print(f"Symbols: {', '.join(config.symbols)}")
    if args.mode == 'bot':
        print(f"Trade Amount: {config.trade_amount_krw:,.0f} KRW")
        print(f"Signal Threshold: {config.signal_threshold}")
        print(f"AI Filter: {'Enabled' if config.use_ai_filter else 'Disabled'}")
        print(f"Dynamic Params: {'Enabled' if config.enable_dynamic_params else 'Disabled'}")
    print("="*60 + "\n")
    
    # 모드별 실행
    try:
        if args.mode == 'bot':
            print("⚠️  WARNING: Real money trading!")
            print("Press Ctrl+C to stop\n")
            asyncio.run(mode_bot(args, config))
        
        elif args.mode == 'backtest':
            asyncio.run(mode_backtest(args, config))
        
        elif args.mode == 'train':
            asyncio.run(mode_train_ai(args, config))
        
        elif args.mode == 'collect':
            asyncio.run(mode_collect(args, config))
    
    except KeyboardInterrupt:
        print("\n\n✋ Stopped by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()