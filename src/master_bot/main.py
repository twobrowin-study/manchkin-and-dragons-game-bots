from telegram.ext import (
    CommandHandler,
    MessageHandler,
    ConversationHandler
)
from telegram.ext.filters import Chat, Text

from loguru import logger

from utils.application import GameApplication
from utils.application_builder import GameApplicationBuilder
from utils.error_handler import error_handler
from utils.config_model import MasterBotConfig

from master_bot.help import help_command_handler

from master_bot.fight_start import (
    FIGHT_START_AWAIT,
    cancel_handler,
    start_fight_handler,
    start_fight_accepted_handler
)

from master_bot.fight import (
    INSPIRATION_AWAIT,
    VULNERABILITY_USE_AWAIT,
    VULNERABILITY_DEF_AWAIT,
    HORDE_INITIATIVE_AWAIT,
    ALLIANCE_INITIATIVE_AWAIT,
    HORDE_ATTACK_AWAIT,
    ALIANCE_ATTACK_AWAIT,
    HORDE_DEF_AWAIT,
    ALIANCE_DEF_AWAIT,
    new_fight_start_handler,
    inspiration_handler,
    vulnerability_use_handler,
    vulnerability_def_handler,
    horde_initiatiative_handler,
    alliance_initiatiative_handler,
    horde_attack_handler,
    alliance_attack_handler,
    horde_defence_handler,
    alliance_defence_handler,
)

if __name__ == "__main__":
    logger.info("Starting now...")
    app: GameApplication = GameApplicationBuilder().name('master').build()
    bot_config: MasterBotConfig = app.bot_config
    chat_id = bot_config.chat_id
    
    app.add_error_handler(error_handler)

    app.add_handler(CommandHandler(app.HELP_COMMAND, help_command_handler, filters=Chat(chat_id)))

    app.add_handler(
        ConversationHandler(
            entry_points = [
                MessageHandler(Chat(chat_id) & Text(app.config.buttons_fun_to_i18n['start_fights']), start_fight_handler)
            ],
            states = {
                FIGHT_START_AWAIT: [
                    MessageHandler(Chat(chat_id) & Text(app.config.buttons_fun_to_i18n['accept']), start_fight_accepted_handler)
                ],
            },
            fallbacks = [
                MessageHandler(Chat(chat_id) & Text(app.config.buttons_fun_to_i18n['cancel']), cancel_handler)
            ]
        ),
    )

    app.add_handler(
        ConversationHandler(
            entry_points = [
                MessageHandler(Chat(chat_id) & Text(app.config.buttons_fun_to_i18n['start_new_fight']), new_fight_start_handler)
            ],
            states = {
                INSPIRATION_AWAIT: [
                    MessageHandler(Chat(chat_id) & Text([
                        app.config.buttons_fun_to_i18n[key] for key in [
                            'horde_inspiration',
                            'alliance_inspiration',
                            'both_inspiration',
                            'none_inspiration',
                        ]
                    ]), inspiration_handler)
                ],

                VULNERABILITY_USE_AWAIT: [
                    MessageHandler(Chat(chat_id) & Text([
                        app.config.buttons_fun_to_i18n[key] for key in [
                            'horde_use_vulnerability',
                            'alliance_use_vulnerability',
                            'both_use_vulnerability',
                            'none_use_vulnerability',
                        ]
                    ]), vulnerability_use_handler)
                ],

                VULNERABILITY_DEF_AWAIT: [
                    MessageHandler(Chat(chat_id) & Text([
                        app.config.buttons_fun_to_i18n[key] for key in [
                            'horde_def_vulnerability',
                            'alliance_def_vulnerability',
                            'both_def_vulnerability',
                            'none_def_vulnerability',
                        ]
                    ]), vulnerability_def_handler)
                ],

                HORDE_INITIATIVE_AWAIT: [
                    MessageHandler(Chat(chat_id) & Text(app.dice_keys), horde_initiatiative_handler)
                ],

                ALLIANCE_INITIATIVE_AWAIT: [
                    MessageHandler(Chat(chat_id) & Text(app.dice_keys), alliance_initiatiative_handler)
                ],

                HORDE_ATTACK_AWAIT: [
                    MessageHandler(Chat(chat_id) & Text(app.dice_keys), horde_attack_handler)
                ],

                ALIANCE_ATTACK_AWAIT: [
                    MessageHandler(Chat(chat_id) & Text(app.dice_keys), alliance_attack_handler)
                ],

                HORDE_DEF_AWAIT: [
                    MessageHandler(Chat(chat_id) & Text(app.dice_keys), horde_defence_handler)
                ],

                ALIANCE_DEF_AWAIT: [
                    MessageHandler(Chat(chat_id) & Text(app.dice_keys), alliance_defence_handler)
                ],

            },
            fallbacks = [
                MessageHandler(Chat(chat_id) & Text(app.config.buttons_fun_to_i18n['cancel']), cancel_handler)
            ]
        )
    )

    logger.info("Starting bot in polling mode...")
    app.run_polling()
    logger.info("Done! Have a great day!")