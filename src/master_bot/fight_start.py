import asyncio
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from sqlalchemy import select, update as sql_update

from loguru import logger
from jinja2 import Template

from utils.application  import GameApplication
from utils.config_model import MasterBotConfig
from utils.db_model import Hero, State
from utils.custom_types import StateEnum

FIGHT_START_AWAIT = 1

async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    chat_id = update.message.chat_id
    logger.info(f"Got cancel from {chat_id=}")
    await update.message.reply_markdown(app.config.i18n.cancel)
    return ConversationHandler.END

async def start_fight_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot_config: MasterBotConfig = app.bot_config
    chat_id = update.message.chat_id

    logger.info(f"Got fight start from {chat_id=}")

    await update.message.reply_markdown(
        bot_config.start_fights.text,
        reply_markup=app.construct_reply_keyboard_markup(bot_config.start_fights.buttons)
    )
    return FIGHT_START_AWAIT

async def start_fight_accepted_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot_config: MasterBotConfig = app.bot_config
    chat_id = update.message.chat_id

    logger.info(f"Got fight start accept from {chat_id=}")

    await update.message.reply_markdown(
        bot_config.fights_started.text,
        reply_markup=app.construct_reply_keyboard_markup(bot_config.fights_started.buttons)
    )

    async with app.db_session() as session:
        await session.execute(
            sql_update(State).values(state = StateEnum.FIGHT)
        )

        heroes_sel = await session.execute(select(Hero))
        heroes = list(heroes_sel.scalars().all())
        template_fight_start = Template(app.config.hero.fight_start.text)

        for hero in heroes:
            await app.send_markdown_to_hero(hero, template_fight_start.render(hero=hero))
        
        await asyncio.sleep(5)
        
        for hero in heroes:
            await app.send_markdown_to_hero(hero, app.config.hero.tutor_fight.text)

        await session.commit()
        
    return ConversationHandler.END