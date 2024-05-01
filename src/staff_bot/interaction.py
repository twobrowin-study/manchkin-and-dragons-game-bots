from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from sqlalchemy import insert, update as sql_update

from loguru import logger
from datetime import datetime

from utils.application  import GameApplication
from utils.config_model import StaffBotConfig
from utils.db_model import Hero, HeroSpecialStationLog
from utils.qr_converter import qr_convert

QR_AWAIT, ABILITY_AWAIT, DICE_AWAIT = 1, 2, 3

async def _reply_error(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot_config: StaffBotConfig = app.bot_config
    await update.message.reply_markdown(app.config.error_message)
    await update.message.reply_markdown(
        bot_config.help.text,
        reply_markup=app.construct_reply_keyboard_markup(bot_config.help.buttons)
    )
    return ConversationHandler.END

async def help_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot_config: StaffBotConfig = app.bot_config
    chat_id = update.message.chat_id

    logger.info(f"Got help command from {chat_id=}")

    await update.message.reply_markdown(
        bot_config.help.text,
        reply_markup=app.construct_reply_keyboard_markup(bot_config.help.buttons)
    )
    return ConversationHandler.END

async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot_config: StaffBotConfig = app.bot_config
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
    bot_config: StaffBotConfig = app.bot_config
    chat_id = update.message.chat_id

    logger.info(f"Got qr start from {chat_id=}")

    await update.message.reply_markdown(
        bot_config.qr.text,
        reply_markup=app.construct_reply_keyboard_markup(bot_config.qr.buttons)
    )
    return QR_AWAIT

async def qr_image_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot_config: StaffBotConfig = app.bot_config
    chat_id = update.message.chat_id

    logger.info(f"Got qr start from {chat_id=}")

    async with app.db_session() as session:
        await update.message.reply_markdown(app.config.i18n.qr_processing)
        
        uuid = await qr_convert(update.message.photo[-1])

        if not uuid:
            logger.warning(f"Staff station {chat_id=} got unkonwn uuid")
            return await _reply_error(update, context)
        
        hero = await app.get_hero_by_uuid(uuid, session)
        if not hero:
            logger.warning(f"Staff station {chat_id=} got unkonwn hero")
            return await _reply_error(update, context)
        
        if hero.times_to_visit_staff == 0:
            logger.info(f"Hero {hero.id} cannot visit staff")
            await update.message.reply_markdown(
                bot_config.no_visit.text.format(hero=hero),
                reply_markup = app.construct_reply_keyboard_markup(bot_config.no_visit.buttons)
            )
            return ConversationHandler.END
            
        await update.message.reply_markdown(
            bot_config.visit.text.format(hero=hero),
            reply_markup = app.construct_reply_keyboard_markup(bot_config.visit.buttons)
        )

        context.chat_data['hero_id'] = hero.id

        await session.commit()

    return ABILITY_AWAIT

async def ability_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot_config: StaffBotConfig = app.bot_config
    chat_id = update.message.chat_id

    logger.info(f"Got ability from {chat_id=}")

    ability_i18n = update.message.text
    ability = app.config.buttons_i18n_to_fun[ability_i18n]

    async with app.db_session() as session:
        hero = await app.get_hero_by_id(context.chat_data['hero_id'], session)
        if not hero or not type(hero) == Hero:
            logger.warning(f"Staff station {chat_id=} got unkonwn hero")
            return await _reply_error(update, context)
                
        await update.message.reply_markdown(
            bot_config.dice.text.format(hero=hero, ability_i18n=ability_i18n),
            reply_markup = app.dice_keyboard
        )

        context.chat_data['ability_i18n'] = ability_i18n
        context.chat_data['ability'] = ability

    return DICE_AWAIT

async def dice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot_config: StaffBotConfig = app.bot_config
    chat_id = update.message.chat_id

    logger.info(f"Got dice from {chat_id=}")

    async with app.db_session() as session:
        hero = await app.get_hero_by_id(context.chat_data['hero_id'], session)
        if not hero or not type(hero) == Hero:
            logger.warning(f"Staff station {chat_id=} got unkonwn hero")
            return await _reply_error(update, context)
        
        ability_i18n: str = context.chat_data['ability_i18n']
        ability: str = context.chat_data['ability']
        
        dice = int(update.message.text)
        result = dice + hero.wisdom

        hero.times_to_visit_staff -= 1

        if dice == 1:
            reply = bot_config.d1
            ability_plus = -1
        elif dice == 20:
            reply = bot_config.d20
            ability_plus = 4
        elif result >= 17:
            reply = bot_config.d17plus
            ability_plus = 3
        elif result >= 11:
            reply = bot_config.d11to16
            ability_plus = 2
        elif result >= 8:
            reply = bot_config.d8to10
            ability_plus = 1
        elif result >= 2:
            reply = bot_config.d2to7
            ability_plus = 0
        
        if ability == 'constitution':
            hero.constitution += ability_plus
        elif ability == 'strength':
            hero.strength += ability_plus
        elif ability == 'dexterity':
            hero.dexterity += ability_plus
        elif ability == 'wisdom':
            hero.wisdom += ability_plus

        await update.message.reply_markdown(
            reply.text.format(hero=hero, dice=dice, result=result, ability_i18n=ability_i18n),
            reply_markup = app.construct_reply_keyboard_markup(reply.buttons)
        )

        next_level = await app.get_hero_next_level(hero, session)

        await app.send_markdown_to_hero(hero, reply.hero.format(hero=hero, next_level=next_level, ability_i18n=ability_i18n))

        await session.execute(
            sql_update(Hero)
            .where(Hero.id == hero.id)
            .values(
                times_to_visit_staff = hero.times_to_visit_staff,
                constitution = hero.constitution,
                strength = hero.strength,
                dexterity = hero.dexterity,
                wisdom = hero.wisdom,
            )
        )

        await session.execute(
            insert(HeroSpecialStationLog)
            .values(
                timestamp = datetime.now(),
                station   = app.name,
                hero_id   = hero.id,
                wisdom    = hero.wisdom,
                dice      = dice,
                ability   = ability,
                ability_plus = ability_plus
            )
        )

        if hero.times_to_visit_staff > 0:
            await app.send_markdown_to_hero(hero, app.config.hero.still_time_to_visit_staff.text)

        await session.commit()

    return ConversationHandler.END