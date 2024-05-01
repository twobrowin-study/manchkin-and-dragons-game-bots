from asyncio import Queue
from typing import Any, Callable, Coroutine
from telegram.ext import Application
from telegram.ext._basepersistence import BasePersistence
from telegram.ext._baseupdateprocessor import BaseUpdateProcessor
from telegram.ext._contexttypes import ContextTypes
from telegram.ext._updater import Updater

from telegram import (
    Bot, BotName,
    BotCommand,
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardRemove,
)
from telegram.constants import ParseMode

from sqlalchemy import select, insert, update as sql_update
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker
)

from loguru import logger
from datetime import datetime

from utils.config_model import ConfigYaml, BotConfig
from utils.minio_client import MinIOClient
from utils.db_model import (
    Base, Level,
    State, StateEnum,
    Hero, Station,
    HeroXpGainLog,
    Monster, FightToUi
)

class GameApplication(Application):
    HELP_COMMAND = 'help'

    def __init__(
            self, *,
            name: str,
            config: ConfigYaml,
            bot_config: BotConfig,
            bot: Any,
            update_queue: Queue[object],
            updater: Updater | None,
            job_queue: Any,
            update_processor: BaseUpdateProcessor,
            persistence: BasePersistence | None,
            context_types: ContextTypes,
            post_init: Callable[[Application], Coroutine[Any, Any, None]] | None,
            post_shutdown: Callable[[Application], Coroutine[Any, Any, None]] | None,
            post_stop: Callable[[Application], Coroutine[Any, Any, None]] | None
        ):
        super().__init__(
            bot=bot,
            update_queue=update_queue,
            updater=updater,
            job_queue=job_queue,
            update_processor=update_processor,
            persistence=persistence,
            context_types=context_types,
            post_init=post_init if post_init else self._post_init,
            post_shutdown=post_shutdown,
            post_stop=post_stop
        )
        self.name       = name
        self.config     = config
        self.bot_config = bot_config
        
        self.db_engine = create_async_engine(
                f"postgresql+asyncpg://{self.config.pg_user}:{self.config.pg_password}@localhost:5432/postgres", 
                echo=False,
                pool_size=10,
                max_overflow=2,
                pool_recycle=300,
                pool_pre_ping=True,
                pool_use_lifo=True
            )
        self.db_session = async_sessionmaker(bind = self.db_engine)
        self.minio      = MinIOClient(self.config.minio_root_user, self.config.minio_root_password, self.config.minio_secure, self.config.minio_host)
        self.dice_keys = list(map(str, range(1, 21)))
        self.dice_keyboard = ReplyKeyboardMarkup([
            [ "1",  "2",  "3",  "4",  "5"],
            [ "6",  "7",  "8",  "9", "10"],
            ["11", "12", "13", "14", "15"],
            ["16", "17", "18", "19", "20"],
            [self.config.buttons_fun_to_i18n['cancel']]
        ])
        
    async def _post_init(self, _: Application) -> None:
        bot: Bot = self.bot
        bot_my_name: BotName = await bot.get_my_name()
        if bot_my_name.name != self.bot_config.my_name:
            await bot.set_my_name(self.bot_config.my_name)
            logger.info("Found difference in my name - updated")

        bot_my_comands: tuple[BotCommand] = await bot.get_my_commands()
        my_commands = (BotCommand(self.HELP_COMMAND, self.config.i18n.help), )
        if bot_my_comands != my_commands:
            await bot.set_my_commands(my_commands)
            logger.info("Found difference in my commands - updated")
        
        if self.name == 'master':
            logger.info("Initializing DB...")
            async with self.db_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            async with self.db_session() as session:
                await self.get_state(session)
                
                if not (await session.execute(select(FightToUi))).scalar_one_or_none():
                    await session.execute(insert(FightToUi))
                
                await session.commit()
    
    def construct_reply_keyboard_markup(self, buttons: list[str]) -> ReplyKeyboardMarkup:
        buttons_len = len(buttons)
        if buttons_len == 0:
            return ReplyKeyboardRemove()
        return ReplyKeyboardMarkup(
            [
                [ self.config.buttons_fun_to_i18n[func_key] for func_key in buttons[idx:idx+2] ]
                for idx in range(0,buttons_len,2)
            ] if buttons_len > 2 \
                else [
                    [ self.config.buttons_fun_to_i18n[func_key] ] for func_key in buttons
                ]
        )
    
    def construct_inline_keyboard_markup(self, buttons: list[str]) -> InlineKeyboardMarkup|None:
        buttons_len = len(buttons)
        if buttons_len == 0:
            return None
        return InlineKeyboardMarkup([
            [ InlineKeyboardButton(text=self.config.buttons_fun_to_i18n[func_key], callback_data=func_key) ]
            for func_key in buttons
        ])

    async def get_state(self, session: AsyncSession) -> StateEnum:
        state_sel = await session.execute(select(State.state).limit(1))
        state = state_sel.scalar_one_or_none()
        if not state:
            await session.execute(insert(State))
            return StateEnum.FAIR
        return state

    async def get_monster_by_id(self, id: int, session: AsyncSession) -> Monster|None:
        monster_sel = await session.execute(
            select(Monster).where(Monster.id == id)
        )
        monster = monster_sel.scalar_one_or_none()
        if not monster:
            return None
        return monster

    async def get_monster_by_uuid(self, uuid: str, session: AsyncSession) -> Monster|None:
        monster_sel = await session.execute(
            select(Monster).where(Monster.uuid == uuid)
        )
        monster = monster_sel.scalar_one_or_none()
        if not monster:
            return None
        return monster
    
    async def get_by_chat_id(self, table: type[Hero|Station], chat_id: int, session: AsyncSession) -> Hero|Station|None:
        sel = await session.execute(
            select(table).where(table.chat_id == chat_id)
        )
        return sel.scalar_one_or_none()

    async def get_hero_next_level(self, hero: Hero, session: AsyncSession) -> Level:
        level_sel = await session.execute(
            select(Level).where(Level.id > hero.level_id).limit(1)
        )
        return level_sel.scalar_one()

    async def get_hero_by_id(self, id: int, session: AsyncSession) -> Hero|None:
        hero_sel = await session.execute(
            select(Hero).where(Hero.id == id)
        )
        hero = hero_sel.scalar_one_or_none()
        if not hero:
            return None
        return hero
        
    async def get_hero_by_uuid(self, uuid: str, session: AsyncSession) -> Hero|None:
        hero_sel = await session.execute(
            select(Hero).where(Hero.uuid == uuid)
        )
        hero = hero_sel.scalar_one_or_none()
        if not hero:
            return None
        return hero
    
    async def gain_hero_xp_by_uuid_and_return_hero(self, uuid: str, xp_gained: int, xp_gain_log_data: dict, session: AsyncSession) -> Hero|None:
        hero = await self.get_hero_by_uuid(uuid, session)
        if not hero:
            return None
        await self.gain_hero_xp(hero, xp_gained, xp_gain_log_data, session)
        return hero
    
    async def gain_hero_xp(self, hero: Hero, xp_gained: int, xp_gain_log_data: dict, session: AsyncSession) -> None:
        next_level = await self.get_hero_next_level(hero, session)
        hero.xp += xp_gained
        
        await self.send_markdown_to_hero(
            hero,
            self.config.hero.gained_xp.text.format(
                xp_gained = xp_gained,
                hero = hero,
                next_level = next_level
            )
        )
        logger.success(f"Hero {hero.id=} gained {xp_gained=} xp")

        # await self.send_markdown_to_master(f"*Клан {hero.id}* получил *{xp_gained}* опыта")
        await session.execute(
            sql_update(Hero).where(Hero.id == hero.id)
            .values(xp = hero.xp)
        )
        
        xp_gain_log_data |= {
            'timestamp': datetime.now(),
            'hero_id':   hero.id,
            'xp_gained': xp_gained
        }

        while hero.xp >= next_level.xp_to_gain:
            hero.xp -= next_level.xp_to_gain
            hero.level_id = next_level.id
            
            next_level = await self.get_hero_next_level(hero, session)
            hero.awaliable_points += 1
            
            logger.success(f"Hero {hero.id=} got level up {hero.level_id=} and {hero.awaliable_points=}")
            
            await self.send_markdown_to_master(f"*Клан {hero.id}* получил *{hero.level_id}* уровень")
            await self.send_markdown_to_hero(
                hero, self.config.hero.level_up.text.format(hero=hero, next_level=next_level),
                reply_markup = self.construct_inline_keyboard_markup(self.config.hero.level_up.inline_buttons)
            )

            if hero.level_id % 3 == 0:
                await self.send_markdown_to_hero(hero, self.config.hero.time_to_visit_staff.text)
                hero.times_to_visit_staff += 1

            if hero.level_id % 5 == 0:
                await self.send_markdown_to_hero(hero, self.config.hero.time_to_visit_colors.text)
                hero.times_to_visit_colors += 1
            
            await session.execute(
                sql_update(Hero).where(Hero.id == hero.id)
                .values(
                    xp                    = hero.xp,
                    level_id              = hero.level_id,
                    awaliable_points      = hero.awaliable_points,
                    times_to_visit_staff  = hero.times_to_visit_staff,
                    times_to_visit_colors = hero.times_to_visit_colors,
                )
            )
            
            xp_gain_log_data |= {
                'level_up_id': hero.level_id
            }
        
        await session.execute(
            insert(HeroXpGainLog).values(**xp_gain_log_data)
        )
        
    async def send_markdown_to_hero(self, hero: Hero, text: str, reply_markup: ReplyKeyboardMarkup|InlineKeyboardMarkup|ReplyKeyboardRemove|None = None) -> None:
        logger.info(f"Sending message to hero {hero.chat_id=} from app {self.name=}")
        await Bot(self.config.hero.token).send_message(
            chat_id=hero.chat_id, text=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def send_markdown_to_master(self, text: str, reply_markup: ReplyKeyboardMarkup|InlineKeyboardMarkup|ReplyKeyboardRemove|None = None) -> None:
        logger.info(f"Sending message to master from app {self.name=}")
        await Bot(self.config.master.token).send_message(
            chat_id=self.config.master.chat_id, text=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
