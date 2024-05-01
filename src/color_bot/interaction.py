from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from sqlalchemy import insert, update as sql_update

from loguru import logger
from datetime import datetime

from utils.application  import GameApplication
from utils.config_model import ColorBotConfig
from utils.db_model import Hero, HeroSpecialStationLog
from utils.qr_converter import qr_convert

QR_AWAIT, DICE_AWAIT = 1, 2

async def _reply_error(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot_config: ColorBotConfig = app.bot_config
    await update.message.reply_markdown(app.config.error_message)
    await update.message.reply_markdown(
        bot_config.help.text,
        reply_markup=app.construct_reply_keyboard_markup(bot_config.help.buttons)
    )
    return ConversationHandler.END

async def help_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot_config: ColorBotConfig = app.bot_config
    chat_id = update.message.chat_id

    logger.info(f"Got help command from {chat_id=}")

    await update.message.reply_markdown(
        bot_config.help.text,
        reply_markup=app.construct_reply_keyboard_markup(bot_config.help.buttons)
    )
    return ConversationHandler.END

async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot_config: ColorBotConfig = app.bot_config
    chat_id = update.message.chat_id

    logger.info(f"Got cancel from {chat_id=}")

    await update.message.reply_markdown(app.config.i18n.cancel)
    await update.message.reply_markdown(
        bot_config.help.text,
        reply_markup=app.construct_reply_keyboard_markup(bot_config.help.buttons)
    )
    return ConversationHandler.END

async def qr_start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot_config: ColorBotConfig = app.bot_config
    chat_id = update.message.chat_id

    logger.info(f"Got qr start from {chat_id=}")

    await update.message.reply_markdown(
        bot_config.qr.text,
        reply_markup=app.construct_reply_keyboard_markup(bot_config.qr.buttons)
    )
    return QR_AWAIT

async def qr_image_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot_config: ColorBotConfig = app.bot_config
    chat_id = update.message.chat_id

    logger.info(f"Got qr start from {chat_id=}")

    async with app.db_session() as session:
        await update.message.reply_markdown(app.config.i18n.qr_processing)
        
        uuid = await qr_convert(update.message.photo[-1])

        if not uuid:
            logger.warning(f"Color station {chat_id=} got unkonwn uuid")
            return await _reply_error(update, context)
        
        hero = await app.get_hero_by_uuid(uuid, session)
        if not hero:
            logger.warning(f"Color station {chat_id=} got unkonwn hero")
            return await _reply_error(update, context)
        
        if hero.times_to_visit_colors == 0:
            logger.info(f"Hero {hero.id} cannot visit colors")
            await update.message.reply_markdown(
                bot_config.no_visit.text.format(hero=hero),
                reply_markup = app.construct_reply_keyboard_markup(bot_config.no_visit.buttons)
            )
            return ConversationHandler.END
            
        await update.message.reply_markdown(
            bot_config.dice.text.format(hero=hero),
            reply_markup=app.dice_keyboard
        )

        context.chat_data['hero_id'] = hero.id

        await session.commit()

    return DICE_AWAIT

async def dice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot_config: ColorBotConfig = app.bot_config
    chat_id = update.message.chat_id

    logger.info(f"Got dice from {chat_id=}")

    async with app.db_session() as session:
        hero = await app.get_hero_by_id(context.chat_data['hero_id'], session)
        if not hero or not type(hero) == Hero:
            logger.warning(f"Color station {chat_id=} got unkonwn hero")
            return await _reply_error(update, context)
        
        dice = int(update.message.text)
        result = dice + hero.wisdom

        hero.times_to_visit_colors -= 1

        if dice == 1:
            reply = bot_config.d1
        elif dice == 20:
            reply = bot_config.d20
        elif result >= 15:
            reply = bot_config.d15plus
        elif result >= 10:
            reply = bot_config.d10to14
        elif result >= 2:
            reply = bot_config.d2to9

        await update.message.reply_markdown(
            reply.text.format(hero=hero, dice=dice, result=result),
            reply_markup = app.construct_reply_keyboard_markup(reply.buttons)
        )

        await app.send_markdown_to_hero(hero, reply.hero)

        await session.execute(
            sql_update(Hero)
            .where(Hero.id == hero.id)
            .values(times_to_visit_colors = hero.times_to_visit_colors)
        )

        await session.execute(
            insert(HeroSpecialStationLog)
            .values(
                timestamp = datetime.now(),
                station   = app.name,
                hero_id   = hero.id,
                wisdom    = hero.wisdom,
                dice      = dice,
            )
        )

        if hero.times_to_visit_colors > 0:
            await app.send_markdown_to_hero(hero, app.config.hero.still_time_to_visit_colors.text)

        await session.commit()

    return ConversationHandler.END