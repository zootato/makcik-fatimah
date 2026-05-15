"""
Mak Cik Fatimah — Singapore Halal Food Finder Bot 🧕🍛
Entry point: sets up the bot, loads data, registers handlers.
"""

import asyncio
import logging
import os

from dotenv import load_dotenv
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
)

from data import HalalData
from handlers import (
    MODE, CUISINE, AREA, HALAL_TYPE,
    start_command,
    help_command,
    random_start,
    handle_mode,
    handle_cuisine,
    handle_area,
    handle_halal_type,
    handle_another,
    random_cancel,
    handle_location,
    nearby_command,
    handle_text,
    stats_command,
)

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATA_SOURCE_URL = os.getenv(
    "DATA_SOURCE_URL",
    "https://raw.githubusercontent.com/zootato/singapore-halal-establishments/main/data/establishments.json",
)
DATA_REFRESH_INTERVAL = int(os.getenv("DATA_REFRESH_INTERVAL", "3600"))
NEARBY_MAX_RESULTS = int(os.getenv("NEARBY_MAX_RESULTS", "5"))


async def post_init(application):
    """Load data after bot init."""
    data = HalalData(
        source_url=DATA_SOURCE_URL,
        refresh_interval=DATA_REFRESH_INTERVAL,
    )
    count = await data.refresh()
    logger.info("Initial data load: %d establishments", count)

    application.bot_data["halal_data"] = data
    application.bot_data["nearby_max_results"] = NEARBY_MAX_RESULTS

    # Background auto-refresh
    asyncio.create_task(data.auto_refresh(application))


def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set! Create a .env file with your token.")
        return

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # ── /random conversation handler ──────────────────────────────────────
    # patterns ensure each handler only fires for its own buttons
    random_conv = ConversationHandler(
        entry_points=[CommandHandler("random", random_start)],
        states={
            MODE: [
                CallbackQueryHandler(handle_mode, pattern="^mode_"),
            ],
            CUISINE: [
                CallbackQueryHandler(handle_cuisine, pattern="^cuisine_"),
            ],
            AREA: [
                CallbackQueryHandler(handle_area, pattern="^area_"),
            ],
            HALAL_TYPE: [
                CallbackQueryHandler(handle_halal_type, pattern="^halal_"),
                CallbackQueryHandler(handle_another, pattern="^another_"),  # ← was missing!
            ],
        },
        fallbacks=[CommandHandler("cancel", random_cancel)],
        allow_reentry=True,
    )

    # ── Register all handlers ─────────────────────────────────────────────
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("nearby", nearby_command))
    app.add_handler(CommandHandler("stats", stats_command))

    app.add_handler(random_conv)

    # Location messages
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))

    # Free text search (must be last)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # ── Start polling ─────────────────────────────────────────────────────
    logger.info("🧕 Mak Cik Fatimah is ready to serve!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()