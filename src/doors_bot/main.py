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
from utils.config_model import DoorsBotConfig

from doors_bot.interaction import (
    QR_AWAIT,
    DOOR_TYPE_AWAIT,
    QUESTION_ANSWER_AWAIT,
    MONSTER_QR_AWAIT,
    ABILITY_AWAIT,
    HERO_DICE_AWAIT,
    MONSTER_DICE_AWAIT,
    help_command_handler,
    cancel_handler,
    qr_start_handler,
    qr_image_handler,
    staff_door_handler,
    question_door_handler,
    answer_correct_handler,
    answer_incorrect_handler,
    monster_start_handler,
    monster_qr_image_handler,
    ability_handler,
    hero_dice_handler,
    monster_dice_handler
)

if __name__ == "__main__":
    logger.info("Starting now...")
    app: GameApplication = GameApplicationBuilder().name('doors').build()
    bot_config: DoorsBotConfig = app.bot_config
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
                DOOR_TYPE_AWAIT: [
                    MessageHandler(Chat(chat_id) & Text(app.config.buttons_fun_to_i18n['staff']),    staff_door_handler),
                    MessageHandler(Chat(chat_id) & Text(app.config.buttons_fun_to_i18n['question']), question_door_handler),
                    MessageHandler(Chat(chat_id) & Text(app.config.buttons_fun_to_i18n['monster']),  monster_start_handler),
                ],
                QUESTION_ANSWER_AWAIT: [
                    MessageHandler(Chat(chat_id) & Text(app.config.buttons_fun_to_i18n['correct']),   answer_correct_handler),
                    MessageHandler(Chat(chat_id) & Text(app.config.buttons_fun_to_i18n['incorrect']), answer_incorrect_handler),
                ],
                MONSTER_QR_AWAIT: [
                    MessageHandler(Chat(chat_id) & PHOTO, monster_qr_image_handler)
                ],
                ABILITY_AWAIT: [
                    MessageHandler(Chat(chat_id) & Text([
                            app.config.buttons_fun_to_i18n[key] for key in ['constitution', 'strength', 'dexterity', 'wisdom']
                        ]), ability_handler),
                ],
                HERO_DICE_AWAIT: [
                    MessageHandler(Chat(chat_id) & Text(app.dice_keys), hero_dice_handler)
                ],
                MONSTER_DICE_AWAIT: [
                    MessageHandler(Chat(chat_id) & Text(app.dice_keys), monster_dice_handler)
                ],
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