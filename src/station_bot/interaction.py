from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from loguru import logger

from utils.application  import GameApplication
from utils.config_model import StationBotConfig
from utils.db_model import Station
from utils.qr_converter import qr_convert

QR_AWAIT= 1

async def _reply_error(update: Update, context: ContextTypes.DEFAULT_TYPE, station: Station) -> int:
    app: GameApplication = context.application
    bot_config: StationBotConfig = app.bot_config
    await update.message.reply_markdown(app.config.error_message)
    await update.message.reply_markdown(
        bot_config.help.text.format(station=station),
        reply_markup=app.construct_reply_keyboard_markup(bot_config.help.buttons)
    )
    return ConversationHandler.END

async def help_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot_config: StationBotConfig = app.bot_config
    chat_id = update.message.chat_id

    logger.info(f"Got help command from {chat_id=}")

    async with app.db_session() as session:
        station = await app.get_by_chat_id(Station, chat_id, session)

        if not station:
            logger.warning(f"Station {chat_id=} was not found")
            return ConversationHandler.END
        
        await update.message.reply_markdown(
            bot_config.help.text.format(station=station),
            reply_markup=app.construct_reply_keyboard_markup(bot_config.help.buttons)
        )
    return ConversationHandler.END

async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot_config: StationBotConfig = app.bot_config
    chat_id = update.message.chat_id

    logger.info(f"Got cancel from {chat_id=}")

    async with app.db_session() as session:
        station = await app.get_by_chat_id(Station, chat_id, session)

        if not station:
            logger.warning(f"Station {chat_id=} was not found")
            return ConversationHandler.END
        
        await update.message.reply_markdown(app.config.i18n.cancel)
        await update.message.reply_markdown(
            bot_config.help.text.format(station=station),
            reply_markup=app.construct_reply_keyboard_markup(bot_config.help.buttons)
        )
    return ConversationHandler.END

async def qr_start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot_config: StationBotConfig = app.bot_config
    chat_id = update.message.chat_id

    logger.info(f"Got qr start from {chat_id=}")

    async with app.db_session() as session:
        station = await app.get_by_chat_id(Station, chat_id, session)

        if not station:
            logger.warning(f"Station {chat_id=} was not found")
            return ConversationHandler.END
        
        await update.message.reply_markdown(
            bot_config.qr.text.format(station=station),
            reply_markup=app.construct_reply_keyboard_markup(bot_config.qr.buttons)
        )
    return QR_AWAIT

async def qr_image_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot_config: StationBotConfig = app.bot_config
    chat_id = update.message.chat_id

    logger.info(f"Got qr start from {chat_id=}")

    async with app.db_session() as session:
        station: Station|None = await app.get_by_chat_id(Station, chat_id, session)

        if not station:
            logger.warning(f"Station {chat_id=} was not found")
            return ConversationHandler.END
        
        await update.message.reply_markdown(app.config.i18n.qr_processing)
        
        uuid = await qr_convert(update.message.photo[-1])

        if not uuid:
            logger.warning("Station {chat_id=} got unkonwn uuid")
            return await _reply_error(update, context, station)
        
        hero = await app.gain_hero_xp_by_uuid_and_return_hero(uuid, station.xp, {'station_id': station.id}, session)
        if not hero:
            logger.warning("Station {chat_id=} got unkonwn hero")
            return await _reply_error(update, context, station)
            
        await update.message.reply_markdown(
            bot_config.success.text.format(station=station, hero=hero),
            reply_markup=app.construct_reply_keyboard_markup(bot_config.success.buttons)
        )

        await session.commit()

    return ConversationHandler.END
