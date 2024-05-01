from telegram import Update
from telegram.ext import ContextTypes

from sqlalchemy import select, update as sql_update
from sqlalchemy.ext.asyncio.session import AsyncSession

from loguru import logger

from jinja2 import Template

from utils.application import GameApplication
from utils.config_model import HeroBotConfig
from utils.db_model import Hero, Level, KnownVulnerability

async def _reply_hero_image_and_save_file_id(update: Update, context: ContextTypes.DEFAULT_TYPE, hero: Hero, session: AsyncSession) -> None:
    app: GameApplication = context.application
    chat_id = update.message.chat_id
    
    if hero.image_file_id:
        logger.info(f"Hero {chat_id=} got image from file_id")
        await update.message.reply_photo(hero.image_file_id)
    
    else:
        logger.info(f"Hero {chat_id=} got image from file")
        question_bio,_ = await app.minio.download(
            bucket=app.config.minio_bucket,
            filename=hero.image
        )
        message = await update.message.reply_photo(question_bio)
        await session.execute(
            sql_update(Hero)
            .where(Hero.id == hero.id)
            .values(image_file_id = message.photo[-1].file_id)
        )

async def _reply_hero_qr_image_and_save_file_id(update: Update, context: ContextTypes.DEFAULT_TYPE, hero: Hero, session: AsyncSession) -> None:
    app: GameApplication = context.application
    bot_config: HeroBotConfig = app.bot_config
    chat_id = update.message.chat_id
    
    if hero.qr_image_file_id:
        logger.info(f"Hero {chat_id=} got qr image from file_id")
        await update.message.reply_photo(
            hero.qr_image_file_id,
            caption=bot_config.qr.text,
            reply_markup=app.construct_reply_keyboard_markup(bot_config.qr.buttons)
        )
    
    else:
        logger.info(f"Hero {chat_id=} got qr image from file")
        question_bio,_ = await app.minio.download(
            bucket=app.config.minio_bucket,
            filename=hero.qr_image
        )
        message = await update.message.reply_photo(
            question_bio,
            caption=bot_config.qr.text,
            reply_markup=app.construct_reply_keyboard_markup(bot_config.qr.buttons)
        )
        await session.execute(
            sql_update(Hero)
            .where(Hero.id == hero.id)
            .values(qr_image_file_id = message.photo[-1].file_id)
        )

async def reply_hero_info(update: Update, context: ContextTypes.DEFAULT_TYPE, hero: Hero, session: AsyncSession) -> None:
    app: GameApplication = context.application
    bot_config: HeroBotConfig = app.bot_config
    next_level = await app.get_hero_next_level(hero, session)
    await _reply_hero_image_and_save_file_id(update, context, hero, session)
    await update.message.reply_markdown(
        bot_config.hero.text.format(hero=hero, next_level=next_level),
        reply_markup = app.construct_reply_keyboard_markup(bot_config.hero.buttons)
    )

async def hero_info_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    app: GameApplication = context.application
    chat_id = update.message.chat_id
    logger.info(f"Hero {chat_id=} got hero info")
    async with app.db_session() as session:
        hero = await app.get_by_chat_id(Hero, chat_id, session)
        if not hero:
            logger.info(f"Hero {chat_id=} was not found")
            return
        await reply_hero_info(update, context, hero, session)
        await session.commit()

async def qr_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    app: GameApplication = context.application
    chat_id = update.message.chat_id
    logger.info(f"Hero {chat_id=} got qr info")
    async with app.db_session() as session:
        hero = await app.get_by_chat_id(Hero, chat_id, session)
        if not hero:
            logger.info(f"Hero {chat_id=} was not found")
            return
        await _reply_hero_qr_image_and_save_file_id(update, context, hero, session)
        await session.commit()

async def known_vulnerabilities_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    app: GameApplication = context.application
    bot_config: HeroBotConfig = app.bot_config
    chat_id = update.message.chat_id
    logger.info(f"Hero {chat_id=} got known vulnerabilities")
    async with app.db_session() as session:
        hero = await app.get_by_chat_id(Hero, chat_id, session)
        if not hero:
            logger.info(f"Hero {chat_id=} was not found")
            return
        
        known_vulnerabilities_sel = await session.execute(
            select(KnownVulnerability)
            .where(
                (KnownVulnerability.wise_hero_id   == hero.id) &
                (KnownVulnerability.target_hero_id != hero.id)
            )
        )
        known_vulnerabilities = list(known_vulnerabilities_sel.scalars())

        known_own_vulnerability_sel = await session.execute(
            select(KnownVulnerability)
            .where(
                (KnownVulnerability.wise_hero_id   == hero.id) &
                (KnownVulnerability.target_hero_id == hero.id)
            )
        )
        known_own_vulnerability = known_own_vulnerability_sel.scalar_one_or_none()

        await update.message.reply_markdown(
            Template(bot_config.known_vulnerabilities.text)
            .render(
                known_vulnerabilities=known_vulnerabilities,
                known_own_vulnerability=known_own_vulnerability,
            ),
            reply_markup = app.construct_reply_keyboard_markup(bot_config.known_vulnerabilities.buttons)
        )

        await session.commit()
