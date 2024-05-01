from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from sqlalchemy import insert, update as sql_update, select

from loguru import logger
from datetime import datetime
from random import choice

from utils.application  import GameApplication
from utils.config_model import GossipBotConfig
from utils.db_model import Hero, KnownVulnerability
from utils.qr_converter import qr_convert

QR_AWAIT, ACCEPT_AWAIT, DICE_AWAIT = 1, 2, 3

async def _reply_error(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot_config: GossipBotConfig = app.bot_config
    await update.message.reply_markdown(app.config.error_message)
    await update.message.reply_markdown(
        bot_config.help.text,
        reply_markup=app.construct_reply_keyboard_markup(bot_config.help.buttons)
    )
    return ConversationHandler.END

async def help_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot_config: GossipBotConfig = app.bot_config
    chat_id = update.message.chat_id

    logger.info(f"Got help command from {chat_id=}")

    await update.message.reply_markdown(
        bot_config.help.text,
        reply_markup=app.construct_reply_keyboard_markup(bot_config.help.buttons)
    )
    return ConversationHandler.END

async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot_config: GossipBotConfig = app.bot_config
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
    bot_config: GossipBotConfig = app.bot_config
    chat_id = update.message.chat_id

    logger.info(f"Got qr start from {chat_id=}")

    await update.message.reply_markdown(
        bot_config.qr.text,
        reply_markup=app.construct_reply_keyboard_markup(bot_config.qr.buttons)
    )
    return QR_AWAIT

async def qr_image_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot_config: GossipBotConfig = app.bot_config
    chat_id = update.message.chat_id

    logger.info(f"Got qr start from {chat_id=}")

    async with app.db_session() as session:
        await update.message.reply_markdown(app.config.i18n.qr_processing)
        
        uuid = await qr_convert(update.message.photo[-1])

        if not uuid:
            logger.warning(f"Gossip station {chat_id=} got unkonwn uuid")
            return await _reply_error(update, context)
        
        hero = await app.get_hero_by_uuid(uuid, session)
        if not hero:
            logger.warning(f"Gossip station {chat_id=} got unkonwn hero")
            return await _reply_error(update, context)
        
        if hero.wisdom == 0:
            logger.info(f"Hero {hero.id} cannot visit colors")
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

    return ACCEPT_AWAIT

async def accept_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot_config: GossipBotConfig = app.bot_config
    chat_id = update.message.chat_id

    logger.info(f"Got accept from {chat_id=}")

    async with app.db_session() as session:
        hero = await app.get_hero_by_id(context.chat_data['hero_id'], session)
        if not hero or not type(hero) == Hero:
            logger.warning(f"Gossip station {chat_id=} got unkonwn hero")
            return await _reply_error(update, context)
            
        hero.wisdom -= 1

        await update.message.reply_markdown(
            bot_config.dice.text.format(hero=hero),
            reply_markup = app.dice_keyboard
        )

        next_level = await app.get_hero_next_level(hero, session)

        await app.send_markdown_to_hero(
            hero, app.config.hero.wisdom_decresed.text.format(hero=hero, next_level=next_level)
        )

        await session.execute(
            sql_update(Hero)
            .where(Hero.id == hero.id)
            .values(wisdom = hero.wisdom)
        )

        await session.commit()
    
    return DICE_AWAIT


async def dice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot_config: GossipBotConfig = app.bot_config
    chat_id = update.message.chat_id

    logger.info(f"Got dice from {chat_id=}")

    async with app.db_session() as session:
        hero = await app.get_hero_by_id(context.chat_data['hero_id'], session)
        if not hero or not type(hero) == Hero:
            logger.warning(f"Gossip station {chat_id=} got unkonwn hero")
            return await _reply_error(update, context)
        
        dice = int(update.message.text)
        result = dice + hero.wisdom

        if dice == 1:
            reply = bot_config.d1
            know_own_vulnerability = False
            know_counterpart_vulnerability = False
            counterpart_know_vulnerability = True
        elif dice == 20:
            reply = bot_config.d20
            know_own_vulnerability = True
            know_counterpart_vulnerability = True
            counterpart_know_vulnerability = False
        elif result >= 17:
            reply = bot_config.d17plus
            know_own_vulnerability = False
            know_counterpart_vulnerability = True
            counterpart_know_vulnerability = False
        elif result >= 11:
            reply = bot_config.d11to16
            know_own_vulnerability = True
            know_counterpart_vulnerability = False
            counterpart_know_vulnerability = False
        elif result >= 2:
            reply = bot_config.d2to10
            know_own_vulnerability = False
            know_counterpart_vulnerability = False
            counterpart_know_vulnerability = False
        
        if not counterpart_know_vulnerability:
            known_vulnerabilities_tagret_ids_sel = await session.execute(
                select(KnownVulnerability.target_hero_id)
                .where(
                    (KnownVulnerability.wise_hero_id == hero.id)
                )
            )
            known_vulnerabilities_tagret_ids = list(known_vulnerabilities_tagret_ids_sel.scalars())

            counterpart_hero_sel = await session.execute(
                select(Hero)
                .where(
                    (Hero.fraction != hero.fraction) &
                    (Hero.id.not_in(known_vulnerabilities_tagret_ids))
                )
            )
            try:
                counterpart_hero = choice(list(counterpart_hero_sel.scalars().all()))
            except Exception:
                await update.message.reply_markdown(
                    bot_config.no_new_gossip.text.format(hero=hero),
                    reply_markup = app.construct_reply_keyboard_markup(bot_config.no_new_gossip.buttons)
                )
                return ConversationHandler.END
        else:
            known_vulnerabilities_wise_ids_sel = await session.execute(
                select(KnownVulnerability.wise_hero_id)
                .where(
                    (KnownVulnerability.target_hero_id == hero.id)
                )
            )
            known_vulnerabilities_wise_ids = list(known_vulnerabilities_wise_ids_sel.scalars())

            counterpart_hero_sel = await session.execute(
                select(Hero)
                .where(
                    (Hero.fraction != hero.fraction) &
                    (Hero.id.not_in(known_vulnerabilities_wise_ids))
                )
            )
            try:
                counterpart_hero = choice(list(counterpart_hero_sel.scalars().all()))
            except Exception:
                await update.message.reply_markdown(
                    bot_config.all_already_know.text.format(hero=hero),
                    reply_markup = app.construct_reply_keyboard_markup(bot_config.all_already_know.buttons)
                )
                return ConversationHandler.END

        await update.message.reply_markdown(
            reply.text.format(hero=hero, counterpart_hero=counterpart_hero, dice=dice, result=result),
            reply_markup = app.construct_reply_keyboard_markup(reply.buttons)
        )

        await app.send_markdown_to_hero(hero, reply.hero.format(hero=hero, counterpart_hero=counterpart_hero))

        if know_own_vulnerability:
            await session.execute(
                insert(KnownVulnerability)
                .values(
                    timestamp = datetime.now(),
                    wise_hero_id   = hero.id,
                    target_hero_id = hero.id,
                )
            )

        if know_counterpart_vulnerability:
            await session.execute(
                insert(KnownVulnerability)
                .values(
                    timestamp = datetime.now(),
                    wise_hero_id   = hero.id,
                    target_hero_id = counterpart_hero.id,
                )
            )

        if counterpart_know_vulnerability:
            await app.send_markdown_to_hero(counterpart_hero, bot_config.counterpart_hero_known_vulnerability.text.format(hero=hero))
            await session.execute(
                insert(KnownVulnerability)
                .values(
                    timestamp = datetime.now(),
                    wise_hero_id   = counterpart_hero.id,
                    target_hero_id = hero.id,
                )
            )

        await session.commit()

    return ConversationHandler.END