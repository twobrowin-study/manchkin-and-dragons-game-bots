from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from sqlalchemy import insert, update as sql_update
from sqlalchemy.ext.asyncio.session import AsyncSession

from loguru import logger
from jinja2 import Template
from datetime import datetime

from utils.application import GameApplication
from utils.config_model import HeroBotConfig
from utils.db_model import Hero, HeroLevelUpLog

ABILITY_INCREASE = 1

async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot_config: HeroBotConfig = app.bot_config
    chat_id = update.message.chat_id

    logger.info(f"Got ability increase from hero {chat_id=}")
    
    async with app.db_session() as session:
        hero = await app.get_by_chat_id(Hero, chat_id, session)
        if not hero:
            logger.info(f"Hero {chat_id=} was not found")
            return ConversationHandler.END
        
        await update.message.reply_markdown(
            app.config.i18n.cancel,
            reply_markup = app.construct_reply_keyboard_markup(bot_config.hero.buttons)
        )
    return ConversationHandler.END

async def level_up_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot_config: HeroBotConfig = app.bot_config
    chat_id = update.effective_chat.id

    logger.info(f"Got ability increase callback from {chat_id=}")
    await update.callback_query.answer()
    
    async with app.db_session() as session:
        hero = await app.get_by_chat_id(Hero, chat_id, session)
        if not hero:
            logger.info(f"Hero {chat_id=} was not found")
            return ConversationHandler.END

        if hero.awaliable_points == 0:
            logger.info(f"Got ability increase callback for hero {chat_id=} while there is no awaliable points")
            await update.effective_message.reply_markdown(
                bot_config.no_awaliable_points.text,
                reply_markup=app.construct_reply_keyboard_markup(bot_config.no_awaliable_points.buttons)
            )
            return ConversationHandler.END

        await update.effective_message.reply_markdown(
            Template(bot_config.ability_increase_start.text).render(hero=hero),
            reply_markup = app.construct_reply_keyboard_markup(bot_config.ability_increase_start.buttons)
        )

        if hero.first_level_up:
            await session.execute(
                sql_update(Hero)
                .where(Hero.id == hero.id)
                .values(first_level_up = False)
            )

        await session.commit()
    
    return ABILITY_INCREASE

async def ability_increase_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot_config: HeroBotConfig = app.bot_config
    chat_id = update.message.chat_id

    logger.info(f"Got ability increase from hero {chat_id=}")

    ability_i18n = update.message.text
    ability = app.config.buttons_i18n_to_fun[ability_i18n]
    
    async with app.db_session() as session:
        hero = await app.get_by_chat_id(Hero, chat_id, session)
        if not hero:
            logger.info(f"Hero {chat_id=} was not found")
            return ConversationHandler.END
        
        if hero.awaliable_points == 0:
            logger.error(f"Got ability increase message for hero {chat_id=} while there is no awaliable points")
            await update.message.reply_markdown(
                bot_config.no_awaliable_points.text,
                reply_markup=app.construct_reply_keyboard_markup(bot_config.no_awaliable_points.buttons)
            )
            return ConversationHandler.END
        
        hero.awaliable_points -= 1
        
        if ability == 'constitution':
            hero.constitution += 1
        elif ability == 'strength':
            hero.strength += 1
        elif ability == 'dexterity':
            hero.dexterity += 1
        elif ability == 'wisdom':
            hero.wisdom += 1
        
        next_level = await app.get_hero_next_level(hero, session)

        await update.effective_message.reply_markdown(
            bot_config.ability_increase_end.text.format(ability_i18n=ability_i18n, hero=hero, next_level=next_level),
            reply_markup = app.construct_reply_keyboard_markup(bot_config.ability_increase_end.buttons)
        )

        await session.execute(
            sql_update(Hero)
            .where(Hero.id == hero.id)
            .values(
                awaliable_points = hero.awaliable_points,
                constitution     = hero.constitution,
                strength         = hero.strength,
                dexterity        = hero.dexterity,
                wisdom           = hero.wisdom,
            )
        )

        if hero.awaliable_points > 0:
            await update.effective_message.reply_markdown(
                bot_config.points_still_awaliable.text.format(hero=hero),
                reply_markup = app.construct_inline_keyboard_markup(bot_config.points_still_awaliable.inline_buttons)
            )
        
        await session.execute(
            insert(HeroLevelUpLog)
            .values(
                timestamp = datetime.now(),
                hero_id           = hero.id,
                increased_ability = ability
            )
        )
        
        # await app.send_markdown_to_master(f"Клан {hero.id} прокачал характеристику {ability_i18n}")

        await session.commit()
    
    return ConversationHandler.END