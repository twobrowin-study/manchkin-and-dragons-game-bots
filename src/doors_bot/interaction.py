from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from sqlalchemy import insert, update as sql_update

from loguru import logger
from datetime import datetime

from utils.application  import GameApplication
from utils.config_model import DoorsBotConfig
from utils.db_model import Hero, HeroDoorLog, Monster
from utils.qr_converter import qr_convert

QR_AWAIT              = 1
DOOR_TYPE_AWAIT       = 2
QUESTION_ANSWER_AWAIT = 3
MONSTER_QR_AWAIT      = 4
ABILITY_AWAIT         = 5
HERO_DICE_AWAIT       = 6
MONSTER_DICE_AWAIT    = 7

async def _reply_error(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot_config: DoorsBotConfig = app.bot_config
    await update.message.reply_markdown(app.config.error_message)
    await update.message.reply_markdown(
        bot_config.help.text,
        reply_markup=app.construct_reply_keyboard_markup(bot_config.help.buttons)
    )
    return ConversationHandler.END

async def help_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot_config: DoorsBotConfig = app.bot_config
    chat_id = update.message.chat_id

    logger.info(f"Got help command from {chat_id=}")

    await update.message.reply_markdown(
        bot_config.help.text,
        reply_markup=app.construct_reply_keyboard_markup(bot_config.help.buttons)
    )
    return ConversationHandler.END

async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot_config: DoorsBotConfig = app.bot_config
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
    bot_config: DoorsBotConfig = app.bot_config
    chat_id = update.message.chat_id

    logger.info(f"Got qr start from {chat_id=}")

    await update.message.reply_markdown(
        bot_config.qr.text,
        reply_markup=app.construct_reply_keyboard_markup(bot_config.qr.buttons)
    )
    return QR_AWAIT

async def qr_image_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot_config: DoorsBotConfig = app.bot_config
    chat_id = update.message.chat_id

    logger.info(f"Got qr image from {chat_id=}")

    async with app.db_session() as session:
        await update.message.reply_markdown(app.config.i18n.qr_processing)
        
        uuid = await qr_convert(update.message.photo[-1])

        if not uuid:
            logger.warning(f"Doors station {chat_id=} got unkonwn uuid")
            return await _reply_error(update, context)
        
        hero = await app.get_hero_by_uuid(uuid, session)
        if not hero:
            logger.warning(f"Doors station {chat_id=} got unkonwn hero")
            return await _reply_error(update, context)
            
        await update.message.reply_markdown(
            bot_config.visit.text.format(hero=hero),
            reply_markup=app.construct_reply_keyboard_markup(bot_config.visit.buttons)
        )

        context.chat_data['hero_id'] = hero.id

        await session.commit()

    return DOOR_TYPE_AWAIT

async def staff_door_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot_config: DoorsBotConfig = app.bot_config
    chat_id = update.message.chat_id

    logger.info(f"Got staff from {chat_id=}")

    async with app.db_session() as session:
        hero = await app.get_hero_by_id(context.chat_data['hero_id'], session)
        if not hero or not type(hero) == Hero:
            logger.warning(f"Doors station {chat_id=} got unkonwn hero")
            return await _reply_error(update, context)

        await update.message.reply_markdown(
            bot_config.staff.text,
            reply_markup=app.construct_reply_keyboard_markup(bot_config.staff.buttons)
        )

        await session.execute(
            insert(HeroDoorLog)
            .values(
                timestamp = datetime.now(),
                hero_id   = hero.id,
                is_staff  = True
            )
        )

        await session.commit()

    return ConversationHandler.END

async def question_door_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot_config: DoorsBotConfig = app.bot_config
    chat_id = update.message.chat_id

    logger.info(f"Got question from {chat_id=}")

    async with app.db_session() as session:
        hero = await app.get_hero_by_id(context.chat_data['hero_id'], session)
        if not hero or not type(hero) == Hero:
            logger.warning(f"Doors station {chat_id=} got unkonwn hero")
            return await _reply_error(update, context)

        await update.message.reply_markdown(
            bot_config.question.text,
            reply_markup=app.construct_reply_keyboard_markup(bot_config.question.buttons)
        )

    return QUESTION_ANSWER_AWAIT

async def answer_correct_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot_config: DoorsBotConfig = app.bot_config
    chat_id = update.message.chat_id
    xp = bot_config.question_xp

    logger.info(f"Got correct answer from {chat_id=}")

    async with app.db_session() as session:
        hero = await app.get_hero_by_id(context.chat_data['hero_id'], session)
        if not hero or not type(hero) == Hero:
            logger.warning(f"Doors station {chat_id=} got unkonwn hero")
            return await _reply_error(update, context)

        await update.message.reply_markdown(
            bot_config.correct.text.format(hero=hero, xp=xp),
            reply_markup=app.construct_reply_keyboard_markup(bot_config.correct.buttons)
        )

        await app.gain_hero_xp(hero, xp, {'monster_id': -1}, session)

        await session.execute(
            insert(HeroDoorLog)
            .values(
                timestamp   = datetime.now(),
                hero_id     = hero.id,
                is_question = True,
                hero_victory    = True
            )
        )

        await session.commit()

    return ConversationHandler.END

async def answer_incorrect_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot_config: DoorsBotConfig = app.bot_config
    chat_id = update.message.chat_id

    logger.info(f"Got incorrect answer from {chat_id=}")

    async with app.db_session() as session:
        hero = await app.get_hero_by_id(context.chat_data['hero_id'], session)
        if not hero or not type(hero) == Hero:
            logger.warning(f"Doors station {chat_id=} got unkonwn hero")
            return await _reply_error(update, context)

        await update.message.reply_markdown(
            bot_config.incorrect.text.format(hero=hero),
            reply_markup=app.construct_reply_keyboard_markup(bot_config.incorrect.buttons)
        )

        await session.execute(
            insert(HeroDoorLog)
            .values(
                timestamp    = datetime.now(),
                hero_id      = hero.id,
                is_question  = True,
                hero_victory = False
            )
        )

        await session.commit()

    return ConversationHandler.END

async def monster_start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot_config: DoorsBotConfig = app.bot_config
    chat_id = update.message.chat_id

    logger.info(f"Got monster start from {chat_id=}")

    async with app.db_session() as session:
        hero = await app.get_hero_by_id(context.chat_data['hero_id'], session)
        if not hero or not type(hero) == Hero:
            logger.warning(f"Doors station {chat_id=} got unkonwn hero")
            return await _reply_error(update, context)

        await update.message.reply_markdown(
            bot_config.monster_qr.text,
            reply_markup=app.construct_reply_keyboard_markup(bot_config.monster_qr.buttons)
        )

    return MONSTER_QR_AWAIT

async def monster_qr_image_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot_config: DoorsBotConfig = app.bot_config
    chat_id = update.message.chat_id

    logger.info(f"Got monster qr from {chat_id=}")

    async with app.db_session() as session:
        await update.message.reply_markdown(app.config.i18n.qr_processing)
        
        uuid = await qr_convert(update.message.photo[-1])

        if not uuid:
            logger.warning(f"Doors station {chat_id=} got unkonwn uuid")
            return await _reply_error(update, context)
        
        monster = await app.get_monster_by_uuid(uuid, session)
        if not monster:
            logger.warning(f"Doors station {chat_id=} got unkonwn monster")
            return await _reply_error(update, context)

        hero = await app.get_hero_by_id(context.chat_data['hero_id'], session)
        if not hero or not type(hero) == Hero:
            logger.warning(f"Doors station {chat_id=} got unkonwn hero")
            return await _reply_error(update, context)
            
        await update.message.reply_markdown(bot_config.hero.text.format(hero=hero))

        await update.message.reply_markdown(
            bot_config.monster.text.format(monster=monster),
            reply_markup=app.construct_reply_keyboard_markup(bot_config.monster.buttons)
        )

        context.chat_data['monster_id'] = monster.id

    return ABILITY_AWAIT

async def ability_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot_config: DoorsBotConfig = app.bot_config
    chat_id = update.message.chat_id

    logger.info(f"Got ability from {chat_id=}")

    ability_i18n = update.message.text
    ability = app.config.buttons_i18n_to_fun[ability_i18n]
    
    async with app.db_session() as session:
        hero = await app.get_hero_by_id(context.chat_data['hero_id'], session)
        if not hero or not type(hero) == Hero:
            logger.warning(f"Doors station {chat_id=} got unkonwn hero")
            return await _reply_error(update, context)
        
        monster = await app.get_monster_by_id(context.chat_data['monster_id'], session)
        if not monster or not type(monster) == Monster:
            logger.warning(f"Doors station {chat_id=} got unkonwn monster")
            return await _reply_error(update, context)
        
        if ability == 'constitution':
            hero_ability    = hero.constitution
            monster_ability = monster.constitution
        elif ability == 'strength':
            hero_ability    = hero.strength
            monster_ability = monster.strength
        elif ability == 'dexterity':
            hero_ability    = hero.dexterity
            monster_ability = monster.dexterity
        elif ability == 'wisdom':
            hero_ability    = hero.wisdom
            monster_ability = monster.wisdom
        
        await update.effective_message.reply_markdown(
            bot_config.ability_hero_dice.text.format(ability_i18n=ability_i18n, hero_ability=hero_ability, monster_ability=monster_ability),
            reply_markup = app.dice_keyboard
        )

        context.chat_data['ability_i18n']    = ability_i18n
        context.chat_data['ability']         = ability
        context.chat_data['hero_ability']    = hero_ability
        context.chat_data['monster_ability'] = monster_ability

    return HERO_DICE_AWAIT

async def hero_dice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot_config: DoorsBotConfig = app.bot_config
    chat_id = update.message.chat_id

    logger.info(f"Got hero dice from {chat_id=}")

    hero_dice = int(update.message.text)
    
    async with app.db_session() as session:
        hero = await app.get_hero_by_id(context.chat_data['hero_id'], session)
        if not hero or not type(hero) == Hero:
            logger.warning(f"Doors station {chat_id=} got unkonwn hero")
            return await _reply_error(update, context)
        
        monster = await app.get_monster_by_id(context.chat_data['monster_id'], session)
        if not monster or not type(monster) == Monster:
            logger.warning(f"Doors station {chat_id=} got unkonwn monster")
            return await _reply_error(update, context)
        
        if hero_dice == 1:
            await update.message.reply_markdown(
                bot_config.d1.text.format(hero=hero),
                reply_markup=app.construct_reply_keyboard_markup(bot_config.d1.buttons)
            )
            await app.send_markdown_to_hero(hero, bot_config.d1.hero.format(monster=monster))
            await session.execute(
                insert(HeroDoorLog)
                .values(
                    timestamp  = datetime.now(),
                    hero_id    = hero.id,
                    monster_id = monster.id,
                    hero_victory   = False
                )
            )
            conversation_state = ConversationHandler.END

        elif hero_dice == 20:
            await update.message.reply_markdown(
                bot_config.d20.text.format(hero=hero),
                reply_markup=app.construct_reply_keyboard_markup(bot_config.d20.buttons)
            )
            await app.send_markdown_to_hero(hero, bot_config.d20.hero.format(monster=monster))
            await app.gain_hero_xp(hero, monster.xp, {'monster_id': monster.id}, session)
            await session.execute(
                insert(HeroDoorLog)
                .values(
                    timestamp    = datetime.now(),
                    hero_id      = hero.id,
                    monster_id   = monster.id,
                    ability      = context.chat_data['ability'],
                    hero_victory = True
                )
            )
            conversation_state = ConversationHandler.END
        
        else:
            await update.message.reply_markdown(
                bot_config.hero_result_monster_dice.text.format(hero=hero, hero_dice=hero_dice),
                reply_markup=app.dice_keyboard
            )
            context.chat_data['hero_dice'] = hero_dice
            conversation_state = MONSTER_DICE_AWAIT

        await session.commit()
    
    return conversation_state

async def monster_dice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot_config: DoorsBotConfig = app.bot_config
    chat_id = update.message.chat_id

    logger.info(f"Got monster dice from {chat_id=}")

    hero_dice    = context.chat_data['hero_dice']
    monster_dice = int(update.message.text)

    ability_i18n = context.chat_data['ability_i18n']
    ability      = context.chat_data['ability']
    
    hero_ability    = context.chat_data['hero_ability']
    monster_ability = context.chat_data['monster_ability']

    hero_result    = hero_dice    + hero_ability
    monster_result = monster_dice + monster_ability

    hero_victory = (hero_result >= monster_result)

    async with app.db_session() as session:
        hero = await app.get_hero_by_id(context.chat_data['hero_id'], session)
        if not hero or not type(hero) == Hero:
            logger.warning(f"Doors station {chat_id=} got unkonwn hero")
            return await _reply_error(update, context)
        
        monster = await app.get_monster_by_id(context.chat_data['monster_id'], session)
        if not monster or not type(monster) == Monster:
            logger.warning(f"Doors station {chat_id=} got unkonwn monster")
            return await _reply_error(update, context)
        
        if hero_victory:
            reply = bot_config.victory
        else:
            reply = bot_config.defeat

        await update.message.reply_markdown(
            reply.text.format(
                hero     = hero,
                monster  = monster,
                
                hero_dice = hero_dice,
                hero_ability = hero_ability,
                hero_result = hero_result,

                monster_dice = monster_dice,
                monster_ability = monster_ability,
                monster_result = monster_result,

                ability_i18n = ability_i18n,

            ),
            reply_markup=app.construct_reply_keyboard_markup(reply.buttons)
        )

        await app.send_markdown_to_hero(hero, reply.hero.format(monster=monster))
        
        if hero_victory:
            await app.gain_hero_xp(hero, monster.xp, {'monster_id': monster.id}, session)

        await session.execute(
            insert(HeroDoorLog)
            .values(
                timestamp    = datetime.now(),
                hero_id      = hero.id,
                monster_id   = monster.id,
                ability      = ability,
                hero_victory = hero_victory
            )
        )

        await session.commit()
    
    return ConversationHandler.END