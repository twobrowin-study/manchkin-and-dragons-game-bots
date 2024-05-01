from telegram.ext import (
    CommandHandler,
    MessageHandler,
    ConversationHandler
)
from telegram.ext.filters import Chat, Text, PHOTO

from loguru import logger

from utils.application import GameApplication
from utils.application_builder import GameApplicationBuilder
from utils.error_handler import error_handler
from utils.config_model import ColorBotConfig

from color_bot.interaction import (
    QR_AWAIT, DICE_AWAIT,
    help_command_handler,
    cancel_handler,
    qr_start_handler,
    qr_image_handler,
    dice_handler
)

if __name__ == "__main__":
    logger.info("Starting now...")
    app: GameApplication = GameApplicationBuilder().name('color').build()
    bot_config: ColorBotConfig = app.bot_config
    chat_id = bot_config.chat_id

    app.add_error_handler(error_handler)

    help_handler = CommandHandler(app.HELP_COMMAND, help_command_handler, filters=Chat(chat_id))

    app.add_handlers([
        ConversationHandler(
            entry_points = [
                MessageHandler(Chat(chat_id) & Text(app.config.buttons_fun_to_i18n['hero_qr']), qr_start_handler)
            ],
            states = {
                QR_AWAIT: [
                    MessageHandler(Chat(chat_id) & PHOTO, qr_image_handler)
                ],
                DICE_AWAIT: [
                    MessageHandler(Chat(chat_id) & Text(app.dice_keys), dice_handler)
                ]
            },
            fallbacks = [
                help_handler,
                MessageHandler(Chat(chat_id) & Text(app.config.buttons_fun_to_i18n['cancel']), cancel_handler)
            ]
        ),
        help_handler
    ])

    logger.info("Starting bot in polling mode...")
    app.run_polling()
    logger.info("Done! Have a great day!")