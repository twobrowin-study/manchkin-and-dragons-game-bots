import asyncio
from telegram import Update, Bot
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode

from sqlalchemy import select, update as sql_update, insert

from loguru import logger
from random import choice
from datetime import datetime
from jinja2 import Template

from utils.application  import GameApplication
from utils.config_model import MasterBotConfig, FightConfig
from utils.db_model     import Hero, FightLog, FightToUi, KnownVulnerability
from utils.custom_types import Fractions

INSPIRATION_AWAIT         = 1
VULNERABILITY_USE_AWAIT   = 2
VULNERABILITY_DEF_AWAIT   = 3
HORDE_INITIATIVE_AWAIT    = 4
ALLIANCE_INITIATIVE_AWAIT = 5
HORDE_ATTACK_AWAIT        = 6
ALIANCE_ATTACK_AWAIT      = 7
HORDE_DEF_AWAIT           = 8
ALIANCE_DEF_AWAIT         = 9

async def _reply_error(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot_config: MasterBotConfig = app.bot_config
    await update.message.reply_markdown(app.config.error_message)
    await update.message.reply_markdown(
        bot_config.help.text,
        reply_markup=app.construct_reply_keyboard_markup(bot_config.help.buttons)
    )
    return ConversationHandler.END

async def send_to_horde_markdown(bot: Bot, fight_config: FightConfig, text: str) -> None:
    await bot.send_message(
        fight_config.horde_chat_id, text,
        parse_mode=ParseMode.MARKDOWN
    )

async def send_to_alliance_markdown(bot: Bot, fight_config: FightConfig, text: str) -> None:
    await bot.send_message(
        fight_config.alliance_chat_id, text,
        parse_mode=ParseMode.MARKDOWN
    )

async def new_fight_start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot: Bot = app.bot
    bot_config:   MasterBotConfig = app.bot_config
    fight_config: FightConfig     = app.config.fight
    chat_id = update.message.chat_id

    logger.info(f"Got new fight start from {chat_id=}")

    async with app.db_session() as session:
        horde_heroes_sel    = await session.execute(
            select(Hero)
            .where(
                (Hero.fraction == Fractions.HORDE) &
                (Hero.has_been_in_fight == False)
            )
        )
        alliance_heroes_sel = await session.execute(
            select(Hero)
            .where(
                (Hero.fraction == Fractions.ALLIANCE) &
                (Hero.has_been_in_fight == False)
            )
        )

        horde_heroes    = list(horde_heroes_sel.scalars().all())
        alliance_heroes = list(alliance_heroes_sel.scalars().all())

        if len(horde_heroes) == 0 or len(alliance_heroes) == 0:
            await update.message.reply_markdown(
                bot_config.no_fight_is_possible.text,
                reply_markup=app.construct_reply_keyboard_markup(bot_config.no_fight_is_possible.buttons)
            )
            return ConversationHandler.END

        horde_hero:    Hero = choice(horde_heroes)
        alliance_hero: Hero = choice(alliance_heroes)

        horde_hero_health    = horde_hero.constitution + 10
        alliance_hero_health = alliance_hero.constitution + 10

        context.chat_data['horde_hero_id']    = horde_hero.id
        context.chat_data['alliance_hero_id'] = alliance_hero.id

        context.chat_data['horde_hero_health']    = horde_hero_health
        context.chat_data['alliance_hero_health'] = alliance_hero_health

        await update.message.reply_markdown(
            bot_config.new_fight_started.text.format(horde_hero=horde_hero, alliance_hero=alliance_hero),
            reply_markup=app.construct_reply_keyboard_markup(bot_config.new_fight_started.buttons)
        )

        await send_to_horde_markdown(bot, fight_config, 
            fight_config.introduction.format(hero = horde_hero, hero_health = horde_hero_health)
        )
        await send_to_alliance_markdown(bot, fight_config, 
            fight_config.introduction.format(hero = alliance_hero, hero_health = alliance_hero_health)
        )

        await session.execute(
            sql_update(Hero)
            .where((Hero.id == horde_hero.id) | (Hero.id == alliance_hero.id))
            .values(has_been_in_fight = True)
        )

        await session.execute(
            insert(FightLog)
            .values(
                timestamp         = datetime.now(),
                horde_hero_id     = horde_hero.id,
                alliance_hero_id  = alliance_hero.id,
                horde_health      = horde_hero_health,
                alliance_health   = alliance_hero_health,
            )
        )

        await session.execute(
            sql_update(FightToUi)
            .values(
                horde_name =          horde_hero.name,
                horde_level =         horde_hero.level_id,
                horde_health =        horde_hero_health,
                horde_constitution =  horde_hero.constitution,
                horde_strength =      horde_hero.strength,
                horde_dexterity =     horde_hero.dexterity,
                horde_wisdom =        horde_hero.wisdom,
                horde_bi =            'clock',
                horde_color =         '#2d2d2d',
                
                alliance_name =          alliance_hero.name,
                alliance_level =         alliance_hero.level_id,
                alliance_health =        alliance_hero_health,
                alliance_constitution =  alliance_hero.constitution,
                alliance_strength =      alliance_hero.strength,
                alliance_dexterity =     alliance_hero.dexterity,
                alliance_wisdom =        alliance_hero.wisdom,
                alliance_bi =            'clock',
                alliance_color =         '#2d2d2d',
            )
        )

        await session.commit()

        return INSPIRATION_AWAIT

async def inspiration_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot: Bot = app.bot
    bot_config:   MasterBotConfig = app.bot_config
    fight_config: FightConfig     = app.config.fight
    chat_id = update.message.chat_id

    logger.info(f"Got inspiration from {chat_id=}")

    inspiration_i18n = update.message.text
    inspiration      = app.config.buttons_i18n_to_fun[inspiration_i18n]

    horde_inspiration    = False
    alliance_inspiration = False

    if inspiration in ['horde_inspiration', 'both_inspiration']:
        horde_inspiration = True

    if inspiration in ['alliance_inspiration', 'both_inspiration']:
        alliance_inspiration = True
    
    context.chat_data['horde_inspiration']    = horde_inspiration
    context.chat_data['alliance_inspiration'] = alliance_inspiration

    async with app.db_session() as session:
        horde_hero = await app.get_hero_by_id(context.chat_data['horde_hero_id'], session)
        if not horde_hero or not type(horde_hero) == Hero:
            logger.warning(f"Fight {chat_id=} got unkonwn horde_hero")
            return await _reply_error(update, context)
        
        alliance_hero = await app.get_hero_by_id(context.chat_data['alliance_hero_id'], session)
        if not alliance_hero or not type(alliance_hero) == Hero:
            logger.warning(f"Fight {chat_id=} got unkonwn alliance_hero")
            return await _reply_error(update, context)

        await update.message.reply_markdown(
            Template(bot_config.inspiration.text)
            .render(
                horde_hero = horde_hero,
                horde_inspiration = horde_inspiration,
                alliance_hero = alliance_hero,
                alliance_inspiration = alliance_inspiration,
            )
        )

        await send_to_horde_markdown(bot, fight_config, 
                                     Template(fight_config.inspiration)
                                     .render(hero=horde_hero, inspiration=horde_inspiration)
                                     )

        await send_to_alliance_markdown(bot, fight_config, 
                                        Template(fight_config.inspiration)
                                        .render(hero=alliance_hero, inspiration=alliance_inspiration)
                                        )

        await session.execute(
            insert(FightLog)
            .values(
                timestamp             = datetime.now(),
                horde_hero_id         = horde_hero.id,
                alliance_hero_id      = alliance_hero.id,
                horde_inspiration     = horde_inspiration,
                alliance_inspiration  = alliance_inspiration,
            )
        )

        await session.execute(
            sql_update(FightToUi)
            .values(
                horde_bi =       'stars' if horde_inspiration else None,
                horde_color =    'blue',
                alliance_bi =    'stars' if alliance_inspiration else None,
                alliance_color = 'blue',
            )
        )

        await session.commit()

    async with app.db_session() as session:
        horde_hero = await app.get_hero_by_id(context.chat_data['horde_hero_id'], session)
        if not horde_hero or not type(horde_hero) == Hero:
            logger.warning(f"Fight {chat_id=} got unkonwn horde_hero")
            return await _reply_error(update, context)
        
        alliance_hero = await app.get_hero_by_id(context.chat_data['alliance_hero_id'], session)
        if not alliance_hero or not type(alliance_hero) == Hero:
            logger.warning(f"Fight {chat_id=} got unkonwn alliance_hero")
            return await _reply_error(update, context)

        horde_know_vulnerability_sel = await session.execute(
            select(KnownVulnerability)
            .where(
                (KnownVulnerability.wise_hero_id   == horde_hero.id) &
                (KnownVulnerability.target_hero_id == alliance_hero.id)
            )
        )
        alliance_know_vulnerability_sel = await session.execute(
            select(KnownVulnerability)
            .where(
                (KnownVulnerability.wise_hero_id   == alliance_hero.id) &
                (KnownVulnerability.target_hero_id == horde_hero.id)
            )
        )

        horde_know_vulnerability    = horde_know_vulnerability_sel.scalar_one_or_none() is not None
        alliance_know_vulnerability = alliance_know_vulnerability_sel.scalar_one_or_none() is not None
    
        context.chat_data['horde_know_vulnerability']    = horde_know_vulnerability
        context.chat_data['alliance_know_vulnerability'] = alliance_know_vulnerability

        await update.message.reply_markdown(
            Template(bot_config.vulnerability_use.text)
            .render(
                horde_hero = horde_hero,
                horde_know_vulnerability = horde_know_vulnerability,
                alliance_hero = alliance_hero,
                alliance_know_vulnerability = alliance_know_vulnerability,
            ),
            reply_markup=app.construct_reply_keyboard_markup(bot_config.vulnerability_use.buttons)
        )

        await send_to_horde_markdown(bot, fight_config, 
                                     Template(fight_config.vulnerability_use)
                                     .render(hero=horde_hero, enemy = alliance_hero,
                                        know_vulnerability=horde_know_vulnerability)
                                     )

        await send_to_alliance_markdown(bot, fight_config, 
                                     Template(fight_config.vulnerability_use)
                                     .render(hero=alliance_hero, enemy = horde_hero,
                                        know_vulnerability=alliance_know_vulnerability)
                                     )

        await session.execute(
            insert(FightLog)
            .values(
                timestamp             = datetime.now(),
                horde_hero_id         = horde_hero.id,
                alliance_hero_id      = alliance_hero.id,
                horde_know_vulnerability    = horde_know_vulnerability,
                alliance_know_vulnerability = alliance_know_vulnerability,
            )
        )

        await session.commit()

    return VULNERABILITY_USE_AWAIT

async def vulnerability_use_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot: Bot = app.bot
    bot_config:   MasterBotConfig = app.bot_config
    fight_config: FightConfig     = app.config.fight
    chat_id = update.message.chat_id

    logger.info(f"Got vulnerability use from {chat_id=}")

    use_vulnerability_i18n = update.message.text
    use_vulnerability      = app.config.buttons_i18n_to_fun[use_vulnerability_i18n]

    horde_use_vulnerability    = False
    alliance_use_vulnerability = False

    if use_vulnerability in ['horde_use_vulnerability', 'both_use_vulnerability']:
        horde_use_vulnerability = True

    if use_vulnerability in ['alliance_use_vulnerability', 'both_use_vulnerability']:
        alliance_use_vulnerability = True
    
    context.chat_data['horde_use_vulnerability']    = horde_use_vulnerability
    context.chat_data['alliance_use_vulnerability'] = alliance_use_vulnerability

    async with app.db_session() as session:
        horde_hero = await app.get_hero_by_id(context.chat_data['horde_hero_id'], session)
        if not horde_hero or not type(horde_hero) == Hero:
            logger.warning(f"Fight {chat_id=} got unkonwn horde_hero")
            return await _reply_error(update, context)
        
        alliance_hero = await app.get_hero_by_id(context.chat_data['alliance_hero_id'], session)
        if not alliance_hero or not type(alliance_hero) == Hero:
            logger.warning(f"Fight {chat_id=} got unkonwn alliance_hero")
            return await _reply_error(update, context)

        await session.execute(
            insert(FightLog)
            .values(
                timestamp             = datetime.now(),
                horde_hero_id         = horde_hero.id,
                alliance_hero_id      = alliance_hero.id,
                horde_use_vulnerability     = horde_use_vulnerability,
                alliance_use_vulnerability  = alliance_use_vulnerability,
            )
        )

        horde_own_vulnerability_sel = await session.execute(
            select(KnownVulnerability)
            .where(
                (KnownVulnerability.wise_hero_id   == horde_hero.id) &
                (KnownVulnerability.target_hero_id == horde_hero.id)
            )
        )
        alliance_own_vulnerability_sel = await session.execute(
            select(KnownVulnerability)
            .where(
                (KnownVulnerability.wise_hero_id   == alliance_hero.id) &
                (KnownVulnerability.target_hero_id == alliance_hero.id)
            )
        )

        horde_own_vulnerability    = horde_own_vulnerability_sel.scalar_one_or_none() is not None
        alliance_own_vulnerability = alliance_own_vulnerability_sel.scalar_one_or_none() is not None
    
        context.chat_data['horde_own_vulnerability']    = horde_own_vulnerability
        context.chat_data['alliance_own_vulnerability'] = alliance_own_vulnerability

        await update.message.reply_markdown(
            Template(bot_config.vulnerability_def.text)
            .render(
                horde_hero = horde_hero,
                horde_own_vulnerability = horde_own_vulnerability,
                alliance_hero = alliance_hero,
                alliance_own_vulnerability = alliance_own_vulnerability,
            ),
            reply_markup=app.construct_reply_keyboard_markup(bot_config.vulnerability_def.buttons)
        )

        await send_to_horde_markdown(bot, fight_config, 
                                     Template(fight_config.vulnerability_def)
                                     .render(hero=horde_hero, own_vulnerability=horde_own_vulnerability)
                                     )

        await send_to_alliance_markdown(bot, fight_config, 
                                     Template(fight_config.vulnerability_def)
                                     .render(hero=alliance_hero, own_vulnerability=alliance_own_vulnerability)
                                     )

        await session.execute(
            insert(FightLog)
            .values(
                timestamp             = datetime.now(),
                horde_hero_id         = horde_hero.id,
                alliance_hero_id      = alliance_hero.id,
                horde_own_vulnerability    = horde_own_vulnerability,
                alliance_own_vulnerability = alliance_own_vulnerability,
            )
        )

        await session.commit()

    return VULNERABILITY_DEF_AWAIT

async def vulnerability_def_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot: Bot = app.bot
    bot_config:   MasterBotConfig = app.bot_config
    fight_config: FightConfig     = app.config.fight
    chat_id = update.message.chat_id

    logger.info(f"Got vulnerability def from {chat_id=}")

    def_vulnerability_i18n = update.message.text
    def_vulnerability      = app.config.buttons_i18n_to_fun[def_vulnerability_i18n]

    horde_def_vulnerability    = False
    alliance_def_vulnerability = False

    if def_vulnerability in ['horde_def_vulnerability', 'both_def_vulnerability']:
        horde_def_vulnerability = True

    if def_vulnerability in ['alliance_def_vulnerability', 'both_def_vulnerability']:
        alliance_def_vulnerability = True
    
    context.chat_data['horde_def_vulnerability']    = horde_def_vulnerability
    context.chat_data['alliance_def_vulnerability'] = alliance_def_vulnerability
    
    horde_use_vulnerability    = context.chat_data['horde_use_vulnerability']
    alliance_use_vulnerability = context.chat_data['alliance_use_vulnerability']

    if alliance_use_vulnerability and not horde_def_vulnerability:
        horde_dexterity_debuf = 5
    elif alliance_use_vulnerability and horde_def_vulnerability:
        horde_dexterity_debuf = 2
    else:
        horde_dexterity_debuf = 0

    if horde_use_vulnerability and not alliance_def_vulnerability:
        alliance_dexterity_debuf = 5
    elif horde_use_vulnerability and alliance_def_vulnerability:
        alliance_dexterity_debuf = 2
    else:
        alliance_dexterity_debuf = 0

    async with app.db_session() as session:
        horde_hero = await app.get_hero_by_id(context.chat_data['horde_hero_id'], session)
        if not horde_hero or not type(horde_hero) == Hero:
            logger.warning(f"Fight {chat_id=} got unkonwn horde_hero")
            return await _reply_error(update, context)
        
        alliance_hero = await app.get_hero_by_id(context.chat_data['alliance_hero_id'], session)
        if not alliance_hero or not type(alliance_hero) == Hero:
            logger.warning(f"Fight {chat_id=} got unkonwn alliance_hero")
            return await _reply_error(update, context)
    
        horde_hero_dexterity    = horde_hero.dexterity    - horde_dexterity_debuf
        alliance_hero_dexterity = alliance_hero.dexterity - alliance_dexterity_debuf
    
        context.chat_data['horde_hero_dexterity']    = horde_hero_dexterity
        context.chat_data['alliance_hero_dexterity'] = alliance_hero_dexterity

        await send_to_horde_markdown(bot, fight_config, 
                                     Template(fight_config.vulnerability_result)
                                     .render(hero=horde_hero, enemy=alliance_hero,
                                             enemy_use_vulnerability=alliance_use_vulnerability,
                                             hero_def_vulnerability=horde_def_vulnerability,
                                             hero_dexterity = horde_hero_dexterity)
                                     )

        await send_to_alliance_markdown(bot, fight_config, 
                                     Template(fight_config.vulnerability_result)
                                     .render(hero=alliance_hero, enemy=horde_hero,
                                             enemy_use_vulnerability=horde_use_vulnerability,
                                             hero_def_vulnerability=alliance_def_vulnerability,
                                             hero_dexterity=alliance_hero_dexterity)
                                     )

        await session.execute(
            insert(FightLog)
            .values(
                timestamp             = datetime.now(),
                horde_hero_id         = horde_hero.id,
                alliance_hero_id      = alliance_hero.id,
                horde_def_vulnerability     = horde_def_vulnerability,
                alliance_def_vulnerability  = alliance_def_vulnerability,
            )
        )

        await session.execute(
            sql_update(FightToUi)
            .values(
                horde_dexterity = horde_hero_dexterity,
                horde_bi =       'slash-circle' if horde_dexterity_debuf else None,
                horde_color =    'red',
                alliance_dexterity = alliance_hero_dexterity,
                alliance_bi =    'slash-circle' if alliance_dexterity_debuf else None,
                alliance_color = 'red',
            )
        )

        await session.commit()

        await update.message.reply_markdown(
            bot_config.horde_initiative.text,
            reply_markup=app.dice_keyboard
        )

    return HORDE_INITIATIVE_AWAIT

async def horde_initiatiative_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot: Bot = app.bot
    bot_config:   MasterBotConfig = app.bot_config
    fight_config: FightConfig     = app.config.fight
    chat_id = update.message.chat_id

    logger.info(f"Got horde initiatiative from {chat_id=}")

    dice = int(update.message.text)
    horde_hero_dexterity = context.chat_data['horde_hero_dexterity']

    async with app.db_session() as session:
        horde_hero = await app.get_hero_by_id(context.chat_data['horde_hero_id'], session)
        if not horde_hero or not type(horde_hero) == Hero:
            logger.warning(f"Fight {chat_id=} got unkonwn horde_hero")
            return await _reply_error(update, context)
        
        alliance_hero = await app.get_hero_by_id(context.chat_data['alliance_hero_id'], session)
        if not alliance_hero or not type(alliance_hero) == Hero:
            logger.warning(f"Fight {chat_id=} got unkonwn alliance_hero")
            return await _reply_error(update, context)
        
        if dice == 1:
            horde_initiatiative = dice
            await send_to_horde_markdown(bot, fight_config, fight_config.d1.format(hero=horde_hero))
            roll_color = 'red'

        elif dice == 20:
            horde_initiatiative = dice + 2 * (horde_hero_dexterity if horde_hero_dexterity >= 2 else 0)
            await send_to_horde_markdown(bot, fight_config, fight_config.d20.format(hero=horde_hero))
            roll_color = 'green'

        else:
            horde_initiatiative = dice + horde_hero_dexterity
            roll_color = '#2d2d2d'
        
        context.chat_data['horde_dice']          = dice
        context.chat_data['horde_initiatiative'] = horde_initiatiative

        await session.execute(
            insert(FightLog)
            .values(
                timestamp        = datetime.now(),
                horde_hero_id    = horde_hero.id,
                alliance_hero_id = alliance_hero.id,
                horde_dice_roll  = dice,
            )
        )
        
        dice_tens = dice//10
        dice_ones = dice%10

        if dice_tens:
            roll_bi = f'{dice_tens}-square\n{dice_ones}-square'
        else:
            roll_bi = f'{dice_ones}-square'

        await session.execute(
            sql_update(FightToUi)
            .values(
                horde_dexterity = horde_hero_dexterity,
                horde_bi =       roll_bi,
                horde_color =    roll_color,
            )
        )

        await session.commit()

        await update.message.reply_markdown(
            bot_config.alliance_initiative.text,
            reply_markup=app.dice_keyboard
        )

    return ALLIANCE_INITIATIVE_AWAIT

async def alliance_initiatiative_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot: Bot = app.bot
    bot_config:   MasterBotConfig = app.bot_config
    fight_config: FightConfig     = app.config.fight
    chat_id = update.message.chat_id

    logger.info(f"Got alliance initiatiative from {chat_id=}")

    dice = int(update.message.text)
    alliance_dice = dice
    alliance_hero_dexterity = context.chat_data['alliance_hero_dexterity']

    horde_initiatiative = context.chat_data['horde_initiatiative']
    horde_hero_dexterity = context.chat_data['horde_hero_dexterity']
    horde_dice = context.chat_data['horde_dice']

    async with app.db_session() as session:
        horde_hero = await app.get_hero_by_id(context.chat_data['horde_hero_id'], session)
        if not horde_hero or not type(horde_hero) == Hero:
            logger.warning(f"Fight {chat_id=} got unkonwn horde_hero")
            return await _reply_error(update, context)
        
        alliance_hero = await app.get_hero_by_id(context.chat_data['alliance_hero_id'], session)
        if not alliance_hero or not type(alliance_hero) == Hero:
            logger.warning(f"Fight {chat_id=} got unkonwn alliance_hero")
            return await _reply_error(update, context)
        
        if dice == 1:
            alliance_initiatiative = dice
            await send_to_alliance_markdown(bot, fight_config, fight_config.d1.format(hero=alliance_hero))
            roll_color = 'red'

        elif dice == 20:
            alliance_initiatiative = dice + 2 * (alliance_hero_dexterity if alliance_hero_dexterity >= 2 else 0)
            await send_to_alliance_markdown(bot, fight_config, fight_config.d20.format(hero=alliance_hero))
            roll_color = 'green'

        else:
            alliance_initiatiative = dice + alliance_hero_dexterity
            roll_color = '#2d2d2d'
        
        context.chat_data['alliance_dice']          = alliance_dice
        context.chat_data['alliance_initiatiative'] = alliance_initiatiative

        await session.execute(
            insert(FightLog)
            .values(
                timestamp          = datetime.now(),
                horde_hero_id      = horde_hero.id,
                alliance_hero_id   = alliance_hero.id,
                alliance_dice_roll = alliance_dice,
            )
        )
        
        dice_tens = dice//10
        dice_ones = dice%10

        if dice_tens:
            roll_bi = f'{dice_tens}-square\n{dice_ones}-square'
        else:
            roll_bi = f'{dice_ones}-square'

        await session.execute(
            sql_update(FightToUi)
            .values(
                alliance_dexterity = alliance_hero_dexterity,
                alliance_bi =       roll_bi,
                alliance_color =    roll_color,
            )
        )

        await session.commit()

    await asyncio.sleep(3)

    async with app.db_session() as session:
        horde_hero = await app.get_hero_by_id(context.chat_data['horde_hero_id'], session)
        if not horde_hero or not type(horde_hero) == Hero:
            logger.warning(f"Fight {chat_id=} got unkonwn horde_hero")
            return await _reply_error(update, context)
        
        alliance_hero = await app.get_hero_by_id(context.chat_data['alliance_hero_id'], session)
        if not alliance_hero or not type(alliance_hero) == Hero:
            logger.warning(f"Fight {chat_id=} got unkonwn alliance_hero")
            return await _reply_error(update, context)

        if horde_initiatiative >= alliance_initiatiative:
            responce  = HORDE_ATTACK_AWAIT
            reply = bot_config.horde_attack
            
            horde_msg    = fight_config.initiative_win
            alliance_msg = fight_config.initiative_loose
            
            horde_bi    = 'magic'
            horde_color = 'green'
            
            alliance_bi    = 'shield'
            alliance_color = '#2d2d2d'
        else:
            responce = ALIANCE_ATTACK_AWAIT
            reply = bot_config.aliance_attack
            
            horde_msg    = fight_config.initiative_loose
            alliance_msg = fight_config.initiative_win
            
            horde_bi    = 'shield'
            horde_color = '#2d2d2d'
            
            alliance_bi    = 'magic'
            alliance_color = 'green'

        await update.message.reply_markdown(reply.text, reply_markup=app.dice_keyboard)

        await send_to_horde_markdown(bot, fight_config, horde_msg.format(
            hero = horde_hero,
            dice = horde_dice,
            hero_dexterity = horde_hero_dexterity,
            result = horde_initiatiative
        ))

        await send_to_alliance_markdown(bot, fight_config, alliance_msg.format(
            hero = alliance_hero,
            dice = alliance_dice,
            hero_dexterity = alliance_hero_dexterity,
            result = alliance_initiatiative
        ))

        await session.execute(
            sql_update(FightToUi)
            .values(
                horde_bi       = horde_bi,
                horde_color    = horde_color,
                alliance_bi    = alliance_bi,
                alliance_color = alliance_color,
            )
        )

        await session.commit()

    return responce

async def horde_attack_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot: Bot = app.bot
    bot_config:   MasterBotConfig = app.bot_config
    fight_config: FightConfig     = app.config.fight
    chat_id = update.message.chat_id

    logger.info(f"Got horde attack from {chat_id=}")

    dice = int(update.message.text)
    horde_dice = dice

    async with app.db_session() as session:
        horde_hero = await app.get_hero_by_id(context.chat_data['horde_hero_id'], session)
        if not horde_hero or not type(horde_hero) == Hero:
            logger.warning(f"Fight {chat_id=} got unkonwn horde_hero")
            return await _reply_error(update, context)
        
        alliance_hero = await app.get_hero_by_id(context.chat_data['alliance_hero_id'], session)
        if not alliance_hero or not type(alliance_hero) == Hero:
            logger.warning(f"Fight {chat_id=} got unkonwn alliance_hero")
            return await _reply_error(update, context)
        
        if dice == 1:
            horde_attack = dice
            await send_to_horde_markdown(bot, fight_config, fight_config.d1.format(hero=horde_hero))
            roll_color = 'red'

        elif dice == 20:
            horde_attack = dice + 2 * horde_hero.strength
            await send_to_horde_markdown(bot, fight_config, fight_config.d20.format(hero=horde_hero))
            roll_color = 'green'

        else:
            horde_attack = dice + horde_hero.strength
            roll_color = '#2d2d2d'
        
        context.chat_data['horde_dice']   = horde_dice
        context.chat_data['horde_attack'] = horde_attack

        await update.message.reply_markdown(bot_config.aliance_def.text, reply_markup=app.dice_keyboard)

        await session.execute(
            insert(FightLog)
            .values(
                timestamp        = datetime.now(),
                horde_hero_id    = horde_hero.id,
                alliance_hero_id = alliance_hero.id,
                horde_dice_roll  = horde_dice,
            )
        )
        
        dice_tens = horde_dice//10
        dice_ones = horde_dice%10

        if dice_tens:
            roll_bi = f'{dice_tens}-square\n{dice_ones}-square'
        else:
            roll_bi = f'{dice_ones}-square'

        await session.execute(
            sql_update(FightToUi)
            .values(
                horde_bi =    roll_bi,
                horde_color = roll_color,
            )
        )

        await session.commit()

    return ALIANCE_DEF_AWAIT

async def alliance_attack_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot: Bot = app.bot
    bot_config:   MasterBotConfig = app.bot_config
    fight_config: FightConfig     = app.config.fight
    chat_id = update.message.chat_id

    logger.info(f"Got alliance attack from {chat_id=}")

    dice = int(update.message.text)
    alliance_dice = dice

    async with app.db_session() as session:
        horde_hero = await app.get_hero_by_id(context.chat_data['horde_hero_id'], session)
        if not horde_hero or not type(horde_hero) == Hero:
            logger.warning(f"Fight {chat_id=} got unkonwn horde_hero")
            return await _reply_error(update, context)
        
        alliance_hero = await app.get_hero_by_id(context.chat_data['alliance_hero_id'], session)
        if not alliance_hero or not type(alliance_hero) == Hero:
            logger.warning(f"Fight {chat_id=} got unkonwn alliance_hero")
            return await _reply_error(update, context)
        
        if dice == 1:
            alliance_attack = dice
            await send_to_alliance_markdown(bot, fight_config, fight_config.d1.format(hero=alliance_hero))
            roll_color = 'red'

        elif dice == 20:
            alliance_attack = dice + 2 * alliance_hero.strength
            await send_to_alliance_markdown(bot, fight_config, fight_config.d20.format(hero=alliance_hero))
            roll_color = 'green'

        else:
            alliance_attack = dice + alliance_hero.strength
            roll_color = '#2d2d2d'
        
        context.chat_data['alliance_dice']   = alliance_dice
        context.chat_data['alliance_attack'] = alliance_attack

        await update.message.reply_markdown(bot_config.horde_def.text, reply_markup=app.dice_keyboard)

        await session.execute(
            insert(FightLog)
            .values(
                timestamp          = datetime.now(),
                horde_hero_id      = horde_hero.id,
                alliance_hero_id   = alliance_hero.id,
                alliance_dice_roll = alliance_dice,
            )
        )
        
        dice_tens = alliance_dice//10
        dice_ones = alliance_dice%10

        if dice_tens:
            roll_bi = f'{dice_tens}-square\n{dice_ones}-square'
        else:
            roll_bi = f'{dice_ones}-square'

        await session.execute(
            sql_update(FightToUi)
            .values(
                alliance_bi =    roll_bi,
                alliance_color = roll_color,
            )
        )

        await session.commit()

    return HORDE_DEF_AWAIT

async def horde_defence_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot: Bot = app.bot
    bot_config:   MasterBotConfig = app.bot_config
    fight_config: FightConfig     = app.config.fight
    chat_id = update.message.chat_id

    logger.info(f"Got horde defence from {chat_id=}")

    dice = int(update.message.text)
    horde_dice = dice

    async with app.db_session() as session:
        horde_hero = await app.get_hero_by_id(context.chat_data['horde_hero_id'], session)
        if not horde_hero or not type(horde_hero) == Hero:
            logger.warning(f"Fight {chat_id=} got unkonwn horde_hero")
            return await _reply_error(update, context)
        
        alliance_hero = await app.get_hero_by_id(context.chat_data['alliance_hero_id'], session)
        if not alliance_hero or not type(alliance_hero) == Hero:
            logger.warning(f"Fight {chat_id=} got unkonwn alliance_hero")
            return await _reply_error(update, context)
        
        if horde_dice == 1:
            horde_defence = horde_dice
            await send_to_horde_markdown(bot, fight_config, fight_config.d1.format(hero=horde_hero))
            roll_color = 'red'

        elif horde_dice == 20:
            horde_defence = horde_dice + 2 * horde_hero.constitution
            await send_to_horde_markdown(bot, fight_config, fight_config.d20.format(hero=horde_hero))
            roll_color = 'green'

        else:
            horde_defence = horde_dice + horde_hero.constitution
            roll_color = '#2d2d2d'
        
        context.chat_data['horde_dice']    = horde_dice
        context.chat_data['horde_defence'] = horde_defence

        await session.execute(
            insert(FightLog)
            .values(
                timestamp        = datetime.now(),
                horde_hero_id    = horde_hero.id,
                alliance_hero_id = alliance_hero.id,
                horde_dice_roll  = horde_dice,
            )
        )
        
        dice_tens = horde_dice//10
        dice_ones = horde_dice%10

        if dice_tens:
            roll_bi = f'{dice_tens}-square\n{dice_ones}-square'
        else:
            roll_bi = f'{dice_ones}-square'

        await session.execute(
            sql_update(FightToUi)
            .values(
                horde_bi =    roll_bi,
                horde_color = roll_color,
            )
        )

        await session.commit()
    
    await asyncio.sleep(3)

    async with app.db_session() as session:
        horde_hero = await app.get_hero_by_id(context.chat_data['horde_hero_id'], session)
        if not horde_hero or not type(horde_hero) == Hero:
            logger.warning(f"Fight {chat_id=} got unkonwn horde_hero")
            return await _reply_error(update, context)
        
        alliance_hero = await app.get_hero_by_id(context.chat_data['alliance_hero_id'], session)
        if not alliance_hero or not type(alliance_hero) == Hero:
            logger.warning(f"Fight {chat_id=} got unkonwn alliance_hero")
            return await _reply_error(update, context)
        
        alliance_dice     = context.chat_data['alliance_dice']
        alliance_attack   = context.chat_data['alliance_attack']
        horde_hero_health = context.chat_data['horde_hero_health']

        atack_result            = alliance_attack - horde_defence
        horde_hero_health_result = horde_hero_health - atack_result

        if atack_result > 0 and horde_hero_health_result > 0:
            horde_health_loose = atack_result
            horde_hero_health  = horde_hero_health_result
            alliance_victory   = False

            responce  = HORDE_ATTACK_AWAIT
            reply = bot_config.horde_attack
            
            horde_msg    = fight_config.def_loose
            alliance_msg = fight_config.atack_win
            
            horde_bi    = 'heartbreak'
            horde_color = 'red'
            
            alliance_bi    = 'magic\ncheck'
            alliance_color = 'green'

            reply_keyboard = app.dice_keyboard

        elif atack_result > 0 and horde_hero_health_result <= 0:
            horde_health_loose = horde_hero_health
            horde_hero_health  = 0
            alliance_victory   = True

            responce  = ConversationHandler.END
            reply = bot_config.aliance_win
            
            horde_msg    = fight_config.defeat
            alliance_msg = fight_config.victory
            
            horde_bi    = 'emoji-dizzy'
            horde_color = 'red'
            
            alliance_bi    = 'magic\ncheck'
            alliance_color = 'green'

            reply_keyboard = app.construct_reply_keyboard_markup(bot_config.fights_started.buttons)

        elif atack_result <= 0:
            horde_health_loose = 0
            horde_hero_health  = horde_hero_health
            alliance_victory   = False

            responce = HORDE_ATTACK_AWAIT
            reply = bot_config.horde_attack
            
            horde_msg    = fight_config.def_win
            alliance_msg = fight_config.atack_loose
            
            horde_bi    = 'shield-check'
            horde_color = 'green'
            
            alliance_bi    = 'magic\ncheck'
            alliance_color = 'red'

            reply_keyboard = app.dice_keyboard
        
        context.chat_data['horde_hero_health'] = horde_hero_health

        await update.message.reply_markdown(reply.text, reply_markup=reply_keyboard)

        await send_to_horde_markdown(bot, fight_config, horde_msg.format(
            hero   = horde_hero,
            dice   = horde_dice,
            result = horde_defence,
            health = horde_hero_health,
            health_loose = horde_health_loose
        ))

        await send_to_alliance_markdown(bot, fight_config, alliance_msg.format(
            hero   = alliance_hero,
            dice   = alliance_dice,
            result = alliance_attack,
            health_loose = horde_health_loose,
        ))

        await session.execute(
            insert(FightLog)
            .values(
                timestamp        = datetime.now(),
                horde_hero_id    = horde_hero.id,
                alliance_hero_id = alliance_hero.id,
                horde_health     = horde_hero_health,
                alliance_victory = alliance_victory
            )
        )

        await session.execute(
            sql_update(FightToUi)
            .values(
                horde_bi       = horde_bi,
                horde_color    = horde_color,
                alliance_bi    = alliance_bi,
                alliance_color = alliance_color,
                horde_health   = horde_hero_health
            )
        )

        await session.commit()

        if not alliance_victory:
            await asyncio.sleep(5)
            async with app.db_session() as session:
                await session.execute(
                    sql_update(FightToUi)
                    .values(
                        horde_bi       = 'magic',
                        horde_color    = 'green',
                        alliance_bi    = 'shield',
                        alliance_color = '#2d2d2d',
                    )
                )
                await session.commit()


    return responce


async def alliance_defence_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    app: GameApplication = context.application
    bot: Bot = app.bot
    bot_config:   MasterBotConfig = app.bot_config
    fight_config: FightConfig     = app.config.fight
    chat_id = update.message.chat_id

    logger.info(f"Got alliance defence from {chat_id=}")

    dice = int(update.message.text)
    alliance_dice = dice

    async with app.db_session() as session:
        horde_hero = await app.get_hero_by_id(context.chat_data['horde_hero_id'], session)
        if not horde_hero or not type(horde_hero) == Hero:
            logger.warning(f"Fight {chat_id=} got unkonwn horde_hero")
            return await _reply_error(update, context)

        alliance_hero = await app.get_hero_by_id(context.chat_data['alliance_hero_id'], session)
        if not alliance_hero or not type(alliance_hero) == Hero:
            logger.warning(f"Fight {chat_id=} got unkonwn alliance_hero")
            return await _reply_error(update, context)
        
        if alliance_dice == 1:
            alliance_defence = alliance_dice
            await send_to_alliance_markdown(bot, fight_config, fight_config.d1.format(hero=alliance_hero))
            roll_color = 'red'

        elif alliance_dice == 20:
            alliance_defence = alliance_dice + 2 * alliance_hero.constitution
            await send_to_alliance_markdown(bot, fight_config, fight_config.d20.format(hero=alliance_hero))
            roll_color = 'green'

        else:
            alliance_defence = alliance_dice + alliance_hero.constitution
            roll_color = '#2d2d2d'
        
        context.chat_data['alliance_dice']    = alliance_dice
        context.chat_data['alliance_defence'] = alliance_defence

        await session.execute(
            insert(FightLog)
            .values(
                timestamp          = datetime.now(),
                horde_hero_id      = horde_hero.id,
                alliance_hero_id   = alliance_hero.id,
                alliance_dice_roll = alliance_dice,
            )
        )
        
        dice_tens = alliance_dice//10
        dice_ones = alliance_dice%10

        if dice_tens:
            roll_bi = f'{dice_tens}-square\n{dice_ones}-square'
        else:
            roll_bi = f'{dice_ones}-square'

        await session.execute(
            sql_update(FightToUi)
            .values(
                alliance_bi =    roll_bi,
                alliance_color = roll_color,
            )
        )

        await session.commit()
    
    await asyncio.sleep(3)

    async with app.db_session() as session:
        horde_hero = await app.get_hero_by_id(context.chat_data['horde_hero_id'], session)
        if not horde_hero or not type(horde_hero) == Hero:
            logger.warning(f"Fight {chat_id=} got unkonwn horde_hero")
            return await _reply_error(update, context)
        
        alliance_hero = await app.get_hero_by_id(context.chat_data['alliance_hero_id'], session)
        if not alliance_hero or not type(alliance_hero) == Hero:
            logger.warning(f"Fight {chat_id=} got unkonwn alliance_hero")
            return await _reply_error(update, context)
        
        horde_dice           = context.chat_data['horde_dice']
        horde_attack         = context.chat_data['horde_attack']
        alliance_hero_health = context.chat_data['alliance_hero_health']

        atack_result           = horde_attack - alliance_defence
        alliance_health_hero_result = alliance_hero_health - atack_result

        if atack_result > 0 and alliance_health_hero_result > 0:
            alliance_health_loose = atack_result
            alliance_hero_health  = alliance_health_hero_result
            horde_victory         = False

            responce  = ALIANCE_ATTACK_AWAIT
            reply = bot_config.aliance_attack
            
            horde_msg    = fight_config.atack_win
            alliance_msg = fight_config.def_loose
            
            horde_bi    = 'magic\ncheck'
            horde_color = 'green'
            
            alliance_bi    = 'heartbreak'
            alliance_color = 'red'

            reply_keyboard = app.dice_keyboard

        elif atack_result > 0 and alliance_health_hero_result <= 0:
            alliance_health_loose = alliance_hero_health
            alliance_hero_health  = 0
            horde_victory         = True

            responce  = ConversationHandler.END
            reply = bot_config.horde_win
            
            horde_msg    = fight_config.victory
            alliance_msg = fight_config.defeat
            
            horde_bi    = 'magic\ncheck'
            horde_color = 'green'
            
            alliance_bi    = 'emoji-dizzy'
            alliance_color = 'red'

            reply_keyboard = app.construct_reply_keyboard_markup(bot_config.fights_started.buttons)

        elif atack_result <= 0:
            alliance_health_loose = 0
            alliance_hero_health  = alliance_hero_health
            horde_victory         = False

            responce = ALIANCE_ATTACK_AWAIT
            reply = bot_config.aliance_attack
            
            horde_msg    = fight_config.atack_loose
            alliance_msg = fight_config.def_win
            
            horde_bi    = 'magic\ncheck'
            horde_color = 'red'
            
            alliance_bi    = 'shield-check'
            alliance_color = 'green'

            reply_keyboard = app.dice_keyboard
        
        context.chat_data['alliance_hero_health'] = alliance_hero_health

        await update.message.reply_markdown(reply.text, reply_markup=reply_keyboard)

        await send_to_horde_markdown(bot, fight_config, horde_msg.format(
            hero   = horde_hero,
            dice   = horde_dice,
            result = horde_attack,
            health_loose = alliance_health_loose,
        ))

        await send_to_alliance_markdown(bot, fight_config, alliance_msg.format(
            hero   = alliance_hero,
            dice   = alliance_dice,
            result = alliance_defence,
            health = alliance_hero_health,
            health_loose = alliance_health_loose,
        ))

        await session.execute(
            insert(FightLog)
            .values(
                timestamp        = datetime.now(),
                horde_hero_id    = horde_hero.id,
                alliance_hero_id = alliance_hero.id,
                alliance_health  = alliance_hero_health,
                horde_victory    = horde_victory
            )
        )

        await session.execute(
            sql_update(FightToUi)
            .values(
                horde_bi        = horde_bi,
                horde_color     = horde_color,
                alliance_bi     = alliance_bi,
                alliance_color  = alliance_color,
                alliance_health = alliance_hero_health
            )
        )

        await session.commit()

        if not horde_victory:
            await asyncio.sleep(5)
            async with app.db_session() as session:
                await session.execute(
                    sql_update(FightToUi)
                    .values(
                        horde_bi       = 'shield',
                        horde_color    = '#2d2d2d',
                        alliance_bi    = 'magic',
                        alliance_color = 'green',
                    )
                )
                await session.commit()

    return responce