import asyncio
from telegram import Update, Bot
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from sqlalchemy import select, insert, update as sql_update
from sqlalchemy.ext.asyncio.session import AsyncSession

from loguru import logger
from datetime import datetime

from utils.application import GameApplication
from utils.config_model import HeroBotConfig
from utils.db_model import Hero, Test, HeroTestLog

from hero_bot.hero import reply_hero_info

async def _reply_voice_and_save_file_id(update: Update, context: ContextTypes.DEFAULT_TYPE, test: Test, session: AsyncSession) -> None:
    app: GameApplication = context.application
    chat_id = update.message.chat_id
    
    if test.question_file_id:
        logger.info(f"Hero {chat_id=} got audio from file_id")
        await update.message.reply_voice(test.question_file_id)
    
    else:
        logger.info(f"Hero {chat_id=} got audio from file")
        question_bio,_ = await app.minio.download(
            bucket=app.config.minio_bucket,
            filename=test.question
        )
        message = await update.message.reply_voice(question_bio)
        await session.execute(
            sql_update(Test)
            .where(Test.id == test.id)
            .values(question_file_id = message.voice.file_id)
        )

async def reply_test(update: Update, context: ContextTypes.DEFAULT_TYPE, test: Test, session: AsyncSession) -> None:
    app: GameApplication = context.application
    bot_config: HeroBotConfig = app.bot_config
    await _reply_voice_and_save_file_id(update, context, test, session)
    await update.message.reply_markdown(
        test.answers_markdown,
        reply_markup=app.construct_reply_keyboard_markup(bot_config.answer_keyboard)
    )

async def _reply_test_and_change_hero_state(update: Update, context: ContextTypes.DEFAULT_TYPE, hero: Hero, test: Test, session: AsyncSession) -> None:
    await reply_test(update, context, test, session)
    await session.execute(
        sql_update(Hero)
        .where(Hero.id == hero.id)
        .values(curr_test_id = test.id)
    )

async def test_start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    app: GameApplication = context.application
    bot: Bot = app.bot
    chat_id = update.message.chat_id

    logger.info(f"Got test start from {chat_id=}")

    async with app.db_session() as session:
        hero = await app.get_by_chat_id(Hero, chat_id, session)

        if not hero:
            logger.warning(f"Hero {chat_id=} was not found")
            return
        
        elif not hero.test_done and not hero.curr_test:
            logger.info(f"Hero {chat_id=} got first question")
            first_test_sel = await session.execute(
                select(Test).order_by(Test.id.asc()).limit(1)
            )
            first_test = first_test_sel.scalar_one()
            await _reply_test_and_change_hero_state(update, context, hero, first_test, session)
            await app.send_markdown_to_master(f"Клан {hero.id} *начал проходить ситуационный тест*")
        
        else:
            logger.info(f"Hero {chat_id=} should not recive first test question")
        
        await session.commit()
    

async def test_answer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    app: GameApplication = context.application
    bot: Bot = app.bot
    bot_config: HeroBotConfig = app.bot_config
    chat_id = update.message.chat_id

    logger.info(f"Got test answer from {chat_id=}")

    async with app.db_session() as session:
        hero = await app.get_by_chat_id(Hero, chat_id, session)

        if not hero:
            logger.warning(f"Hero {chat_id=} was not found")
            return

        if not hero.curr_test:
            logger.warning(f"Hero {chat_id=} send answer to unknown question")
            await app.send_markdown_to_master(f"🚨 Внимание! Клан {hero.id} *ответил на несуществующий вопрос*")
            return
        
        if hero.test_done:
            logger.warning(f"Hero {chat_id=} already answered to all questions")
            await app.send_markdown_to_master(f"🚨 Внимание! Клан {hero.id} *выслал ответ когда вопросы уже не заданы*")
            return

        await session.execute(
            insert(HeroTestLog).
            values(
                timestamp = datetime.now(),
                hero_id = hero.id,
                test_id = hero.curr_test_id,
                answer  = update.message.text
            )
        )
        await app.send_markdown_to_master(f"Клан {hero.id} *ответил на вопрос {hero.curr_test_id}*")

        next_test_sel = await session.execute(
            select(Test)
            .where(Test.id > hero.curr_test_id)
            .limit(1)
        )
        next_test = next_test_sel.scalar_one_or_none()

        if next_test:
            logger.info(f"Hero {chat_id=} got next test")
            await _reply_test_and_change_hero_state(update, context, hero, next_test, session)
        
        else:
            logger.info(f"Hero {chat_id=} has done all tests")
            await update.message.reply_markdown(
                bot_config.last_test.text,
                reply_markup=app.construct_reply_keyboard_markup(bot_config.last_test.buttons)
            )
            await reply_hero_info(update, context, hero, session)
            await session.execute(
                sql_update(Hero)
                .where(Hero.id == hero.id)
                .values(
                    curr_test_id = None,
                    test_done = True
                )
            )
            await app.send_markdown_to_master(f"Клан {hero.id} *закончил проходить ситуационный тест*")
            await bot.send_message(
                chat_id, bot_config.tutorial_first_level.text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=app.construct_reply_keyboard_markup(bot_config.tutorial_first_level.buttons)
            )
        await session.commit()
        
