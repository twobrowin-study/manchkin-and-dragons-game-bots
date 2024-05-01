from telegram.ext import (
    CommandHandler,
    MessageHandler,
    ConversationHandler
)
from telegram.ext.filters import ChatType, Text, PHOTO

from loguru import logger

from utils.application import GameApplication
from utils.application_builder import GameApplicationBuilder
from utils.error_handler import error_handler

from station_bot.interaction import (
    QR_AWAIT,
    help_command_handler,
    cancel_handler,
    qr_start_handler,
    qr_image_handler,
)

if __name__ == "__main__":
    logger.info("Starting now...")
    app: GameApplication = GameApplicationBuilder().name('station').build()

    app.add_error_handler(error_handler)

    help_handler = CommandHandler(app.HELP_COMMAND, help_command_handler, filters=ChatType.GROUPS)

    app.add_handlers([
        ConversationHandler(
            entry_points = [
                MessageHandler(ChatType.GROUPS & Text(app.config.buttons_fun_to_i18n['hero_qr']), qr_start_handler)
            ],
            states = {
                QR_AWAIT: [
                    MessageHandler(ChatType.GROUPS & PHOTO, qr_image_handler)
                ]
            },
            fallbacks = [
                help_handler,
                MessageHandler(ChatType.GROUPS & Text(app.config.buttons_fun_to_i18n['cancel']), cancel_handler)
            ]
        ),
        help_handler
    ])

    logger.info("Starting bot in polling mode...")
    app.run_polling()
    logger.info("Done! Have a great day!")