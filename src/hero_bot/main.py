from telegram.ext import (
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackQueryHandler
)
from telegram.ext.filters import ChatType, Text

from loguru import logger

from utils.application import GameApplication
from utils.application_builder import GameApplicationBuilder
from utils.error_handler import error_handler

from hero_bot.help import help_command_handler
from hero_bot.test import test_start_handler, test_answer_handler
from hero_bot.hero import hero_info_handler, qr_handler, known_vulnerabilities_handler
from hero_bot.level_up import (
    ABILITY_INCREASE,
    cancel_handler,
    level_up_callback_handler,
    ability_increase_handler
)

if __name__ == "__main__":
    logger.info("Starting now...")
    app: GameApplication = GameApplicationBuilder().name('hero').build()

    app.add_error_handler(error_handler)

    app.add_handler(ConversationHandler(
        entry_points = [
            CallbackQueryHandler(level_up_callback_handler, pattern='ability_increase')
        ],
        states = {
            ABILITY_INCREASE: [
                MessageHandler(ChatType.GROUPS & Text([
                    app.config.buttons_fun_to_i18n[key] for key in ['constitution', 'strength', 'dexterity', 'wisdom']
                ]), ability_increase_handler),
            ]
        },
        fallbacks = [
            MessageHandler(ChatType.GROUPS & Text(app.config.buttons_fun_to_i18n['cancel']), cancel_handler),
        ]
    ))

    app.add_handler(CommandHandler(app.HELP_COMMAND, help_command_handler, filters=ChatType.GROUPS))

    app.add_handlers([
        MessageHandler(ChatType.GROUPS & Text(app.config.buttons_fun_to_i18n['start']), test_start_handler),
        MessageHandler(ChatType.GROUPS & Text([
            app.config.buttons_fun_to_i18n[key] for key in ['answer_1', 'answer_2', 'answer_3', 'answer_4']
        ]), test_answer_handler),
    ])

    app.add_handlers([
        MessageHandler(ChatType.GROUPS & Text(app.config.buttons_fun_to_i18n['hero']), hero_info_handler),
        MessageHandler(ChatType.GROUPS & Text(app.config.buttons_fun_to_i18n['qr']), qr_handler),
        MessageHandler(ChatType.GROUPS & Text(app.config.buttons_fun_to_i18n['known_vulnerabilities']), known_vulnerabilities_handler),
    ])

    logger.info("Starting bot in polling mode...")
    app.run_polling()
    logger.info("Done! Have a great day!")