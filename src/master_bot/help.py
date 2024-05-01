from telegram import Update
from telegram.ext import ContextTypes

from loguru import logger

from utils.application  import GameApplication
from utils.config_model import MasterBotConfig
from utils.custom_types import StateEnum

async def help_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    app: GameApplication = context.application
    bot_config: MasterBotConfig = app.bot_config
    chat_id = update.message.chat_id

    logger.info(f"Got help command from {chat_id=}")

    async with app.db_session() as session:
        help_buttons = bot_config.help.buttons
        state = await app.get_state(session)
        if state == StateEnum.FIGHT:
            help_buttons = bot_config.fights_started.buttons

        await update.message.reply_markdown(
            bot_config.help.text,
            reply_markup=app.construct_reply_keyboard_markup(help_buttons)
        )