from telegram import Update
from telegram.ext import ContextTypes

from loguru import logger
from jinja2 import Template

from utils.application  import GameApplication
from utils.config_model import HeroBotConfig
from utils.custom_types import StateEnum
from utils.db_model     import Hero

from hero_bot.test import reply_test

async def help_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    app: GameApplication = context.application
    bot_config: HeroBotConfig = app.bot_config
    chat_id = update.message.chat_id

    logger.info(f"Got help command from {chat_id=}")

    async with app.db_session() as session:
        hero: Hero = await app.get_by_chat_id(Hero, chat_id, session)
        state      = await app.get_state(session)

        if not hero:
            logger.warning(f"Hero {chat_id=} was not found")
            return
        
        if not hero.test_done and not hero.curr_test:
            logger.info(f"Hero {chat_id=} got greeting")
            await update.message.reply_markdown(
                bot_config.greeting.text,
                reply_markup=app.construct_reply_keyboard_markup(bot_config.greeting.buttons)
            )
            return

        if not hero.test_done and hero.curr_test:
            logger.info(f"Hero {chat_id=} got test help")
            await update.message.reply_markdown(bot_config.test.text)
            await reply_test(update, context, hero.curr_test, session)
            return
        
        if hero.test_done and state == StateEnum.FAIR:
            logger.info(f"Hero {chat_id=} got fair help")
            await update.message.reply_markdown(
                bot_config.fair.text,
                reply_markup=app.construct_reply_keyboard_markup(bot_config.fair.buttons)
            )
            return
        
        if hero.test_done and state == StateEnum.FIGHT:
            logger.info(f"Hero {chat_id=} got fight help")
            await update.message.reply_markdown(
                Template(bot_config.fight.text).render(hero=hero),
                reply_markup=app.construct_reply_keyboard_markup(bot_config.fight.buttons)
            )
            return
        
        await session.commit()