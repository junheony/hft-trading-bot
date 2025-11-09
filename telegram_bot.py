"""
HFT Bot v0.7 - Telegram Bot Module
양방향 제어 (알림 + 명령어)
"""

import asyncio
from typing import Optional, Dict, Any

try:
    from telegram import Bot, Update
    from telegram.ext import Application, CommandHandler, ContextTypes
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False

from core import TradingConfig, Position, Trade, Logger


class TelegramBot:
    """
    텔레그램 봇
    - 실시간 알림
    - 양방향 제어 (/status, /stop, /start)
    """
    
    def __init__(self, config: TradingConfig, logger: Logger):
        self.config = config
        self.logger = logger
        self.bot: Optional[Bot] = None
        self.app: Optional[Application] = None
        self.chat_id = config.telegram_chat_id
        
        # 봇 제어 참조 (나중에 설정)
        self.bot_controller = None
        
        if not TELEGRAM_AVAILABLE:
            logger.warning("Telegram not available")
            return
        
        if not config.telegram_token or not config.telegram_chat_id:
            logger.warning("Telegram credentials not configured")
            return
        
        self.bot = Bot(token=config.telegram_token)
    
    def set_bot_controller(self, controller):
        """봇 컨트롤러 설정 (순환 참조 방지)"""
        self.bot_controller = controller
    
    async def send_message(self, message: str):
        """메시지 전송"""
        if not self.bot or not self.chat_id:
            return
        
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='HTML'
            )
        except Exception as e:
            self.logger.error(f"Telegram send failed: {e}")
    
    async def notify_entry(self, position: Position):
        """진입 알림"""
        ind = position.indicators
        
        msg = (
            f"🟢 <b>ENTRY</b>\n"
            f"Symbol: {position.symbol}\n"
            f"Side: {position.side.value}\n"
            f"Price: {position.entry_price:,.0f} KRW\n"
            f"Amount: {position.amount:.6f}\n"
            f"Signal Score: {position.signal_score:.3f}\n"
            f"\n"
            f"Indicators:\n"
            f"• Z-Score: {ind.get('wobi_z', 0):.2f}\n"
            f"• RSI: {ind.get('rsi', 0):.1f}\n"
            f"• MACD: {ind.get('macd', 0):.3f}\n"
            f"• BB Pos: {ind.get('bb_position', 0):.2f}\n"
            f"• Stoch: {ind.get('stoch_k', 0):.1f}"
        )
        
        await self.send_message(msg)
    
    async def notify_exit(self, trade: Trade):
        """청산 알림"""
        emoji = "📈" if trade.pnl > 0 else "📉"
        
        msg = (
            f"🔴 <b>EXIT</b> {emoji}\n"
            f"Symbol: {trade.symbol}\n"
            f"PnL: {trade.pnl:,.0f} KRW\n"
            f"Return: {(trade.pnl / (trade.entry_price * trade.amount) * 100):.2f}%\n"
            f"Reason: {trade.exit_reason.value}\n"
            f"Hold Time: {trade.holding_seconds:.1f}s\n"
            f"Entry: {trade.entry_price:,.0f} → Exit: {trade.exit_price:,.0f}"
        )
        
        await self.send_message(msg)
    
    async def notify_daily_report(self, stats: Dict[str, Any]):
        """일일 리포트"""
        msg = (
            f"📊 <b>Daily Report</b>\n"
            f"Date: {stats['date']}\n"
            f"\n"
            f"PnL: {stats['pnl']:,.0f} KRW\n"
            f"Peak PnL: {stats['peak_pnl']:,.0f} KRW\n"
            f"Drawdown: {stats['drawdown']:,.0f} KRW\n"
            f"\n"
            f"Trades: {stats['trades']}\n"
            f"Win Rate: {stats['win_rate']*100:.1f}%\n"
            f"Wins: {stats['wins']} | Losses: {stats['losses']}\n"
            f"Consecutive Losses: {stats['consecutive_losses']}"
        )
        
        await self.send_message(msg)
    
    async def notify_emergency(self, message: str):
        """긴급 알림"""
        msg = f"🚨 <b>EMERGENCY</b>\n\n{message}"
        await self.send_message(msg)
    
    # === 명령어 핸들러 ===
    
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /status 명령어
        현재 봇 상태 조회
        """
        if not self.bot_controller:
            await update.message.reply_text("Bot controller not set")
            return
        
        stats = self.bot_controller.get_status()
        
        msg = (
            f"📊 <b>Bot Status</b>\n"
            f"\n"
            f"Status: {stats['status']}\n"
            f"Active Positions: {stats['positions_count']}\n"
            f"Daily PnL: {stats['daily_pnl']:,.0f} KRW\n"
            f"Win Rate: {stats['win_rate']*100:.1f}%"
        )
        
        await update.message.reply_text(msg, parse_mode='HTML')
    
    async def cmd_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /stop 명령어
        봇 긴급 중지
        """
        if not self.bot_controller:
            await update.message.reply_text("Bot controller not set")
            return
        
        await self.bot_controller.emergency_stop("User command")
        await update.message.reply_text("🛑 Bot stopped")
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /start 명령어
        긴급 중지 해제
        """
        if not self.bot_controller:
            await update.message.reply_text("Bot controller not set")
            return
        
        self.bot_controller.resume()
        await update.message.reply_text("✅ Bot resumed")
    
    async def cmd_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /positions 명령어
        현재 포지션 목록
        """
        if not self.bot_controller:
            await update.message.reply_text("Bot controller not set")
            return
        
        positions = self.bot_controller.get_positions()
        
        if not positions:
            await update.message.reply_text("No active positions")
            return
        
        msg = "<b>Active Positions</b>\n\n"
        for pos in positions:
            msg += (
                f"• {pos.symbol} | {pos.side.value}\n"
                f"  Entry: {pos.entry_price:,.0f} KRW\n"
                f"  Score: {pos.signal_score:.3f}\n\n"
            )
        
        await update.message.reply_text(msg, parse_mode='HTML')
    
    def setup_handlers(self):
        """명령어 핸들러 설정"""
        if not TELEGRAM_AVAILABLE or not self.config.telegram_token:
            return
        
        self.app = Application.builder().token(self.config.telegram_token).build()
        
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        self.app.add_handler(CommandHandler("stop", self.cmd_stop))
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("positions", self.cmd_positions))
        
        self.logger.info("Telegram handlers registered")
    
    async def run_polling(self):
        """폴링 시작 (백그라운드)"""
        if not self.app:
            return
        
        try:
            await self.app.initialize()
            await self.app.start()
            await self.app.updater.start_polling()
            
            self.logger.info("Telegram polling started")
            
            # 무한 대기
            while True:
                await asyncio.sleep(1)
        except Exception as e:
            self.logger.error(f"Telegram polling error: {e}")