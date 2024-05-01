from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    BigInteger
)
from sqlalchemy.orm import (
    MappedAsDataclass, 
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship
)
from utils.custom_types import (
    StateEnum,
    Fractions
)

from datetime import datetime

class Base(MappedAsDataclass, DeclarativeBase):
    pass

class State(Base):
    __tablename__ = "state"
    id:    Mapped[int]       = mapped_column(primary_key=True, nullable=False)
    state: Mapped[StateEnum] = mapped_column(nullable=False,   default=StateEnum.FAIR)

class Test(Base):
    __tablename__ = "tests"
    id:               Mapped[int]      = mapped_column(primary_key=True, nullable=False)
    question:         Mapped[str]      = mapped_column(nullable=False,   default=None)
    question_file_id: Mapped[str|None] = mapped_column(nullable=True,    default=None)
    answers_markdown: Mapped[str]      = mapped_column(nullable=False,   default=None)

class Level(Base):
    __tablename__ = "levels"

    id:         Mapped[int] = mapped_column(primary_key=True, nullable=False)
    xp_to_gain: Mapped[int] = mapped_column(nullable=False,   default=None)

class Hero(Base):
    __tablename__ = "heroes"

    id:      Mapped[int] = mapped_column(primary_key=True, nullable=False)
    chat_id: Mapped[int] = mapped_column(nullable=False,   index=True, unique=True, type_=BigInteger)
    
    curr_test_id: Column[int] = Column(Integer, ForeignKey(Test.id), nullable=True)
    curr_test = relationship('Test', lazy='selectin')
    test_done:    Mapped[bool] = mapped_column(nullable=False, default=False)

    name:          Mapped[str] = mapped_column(nullable=False, default=None)
    image:         Mapped[str] = mapped_column(nullable=False, default=None)
    image_file_id: Mapped[str] = mapped_column(nullable=True,  default=None)

    description: Mapped[str] = mapped_column(nullable=False, default=None)
    
    fraction: Mapped[Fractions] = mapped_column(nullable=False, default=None)

    vulnerability: Mapped[str] = mapped_column(nullable=False, default=None)

    uuid:             Mapped[str] = mapped_column(nullable=False, default=None)
    qr_image:         Mapped[str] = mapped_column(nullable=False, default=None)
    qr_image_file_id: Mapped[str] = mapped_column(nullable=True,  default=None)

    level_id: Column[int] = Column(Integer, ForeignKey(Level.id), nullable=False)
    level = relationship('Level', lazy='selectin')

    xp: Mapped[int] = mapped_column(nullable=False, default=None)

    constitution: Mapped[int] = mapped_column(nullable=False, default=None)
    strength:     Mapped[int] = mapped_column(nullable=False, default=None)
    dexterity:    Mapped[int] = mapped_column(nullable=False, default=None)
    wisdom:       Mapped[int] = mapped_column(nullable=False, default=None)

    awaliable_points:      Mapped[int]  = mapped_column(nullable=False, default=0)
    times_to_visit_staff:  Mapped[int]  = mapped_column(nullable=False, default=0)
    times_to_visit_colors: Mapped[int]  = mapped_column(nullable=False, default=0)
    first_level_up:        Mapped[bool] = mapped_column(nullable=False, default=True)

    has_been_in_fight: Mapped[bool] = mapped_column(nullable=False, default=False)

class KnownVulnerability(Base):
    __tablename__ = "known_vulnerabilities"
    id: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(nullable=False, default=None)
    
    wise_hero_id:   Column[int] = Column(Integer, ForeignKey(Hero.id), nullable=False)
    target_hero_id: Column[int] = Column(Integer, ForeignKey(Hero.id), nullable=False)
    target = relationship('Hero', lazy='selectin', foreign_keys=target_hero_id)

class Station(Base):
    __tablename__ = "stations"
    id:      Mapped[int] = mapped_column(primary_key=True, nullable=False)
    chat_id: Mapped[int] = mapped_column(nullable=False,   index=True, unique=True, type_=BigInteger)

    name: Mapped[str] = mapped_column(nullable=False, default=None)
    xp:   Mapped[int] = mapped_column(nullable=False, default=None)

class Monster(Base):
    __tablename__ = "monsters"
    id:          Mapped[int] = mapped_column(primary_key=True, nullable=False)
    uuid:        Mapped[str] = mapped_column(nullable=False, default=None)
    
    name:        Mapped[str] = mapped_column(nullable=False, default=None)
    description: Mapped[str] = mapped_column(nullable=False, default=None)
    
    level_id:    Mapped[int] = mapped_column(nullable=False, default=None)
    xp:          Mapped[int] = mapped_column(nullable=False, default=None)

    constitution: Mapped[int] = mapped_column(nullable=False, default=None)
    strength:     Mapped[int] = mapped_column(nullable=False, default=None)
    dexterity:    Mapped[int] = mapped_column(nullable=False, default=None)
    wisdom:       Mapped[int] = mapped_column(nullable=False, default=None)

class HeroTestLog(Base):
    __tablename__ = "hero_test_logs"
    id:        Mapped[int]      = mapped_column(primary_key=True, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(nullable=False, default=None)
    hero_id:   Mapped[int]      = mapped_column(nullable=False, default=None)
    test_id:   Mapped[int]      = mapped_column(nullable=False, default=None)
    answer:    Mapped[str]      = mapped_column(nullable=False, default=None)

class HeroXpGainLog(Base):
    __tablename__ = "hero_xp_gain_logs"
    id:          Mapped[int]      = mapped_column(primary_key=True, nullable=False)
    timestamp:   Mapped[datetime] = mapped_column(nullable=False, default=None)
    hero_id:     Mapped[int]      = mapped_column(nullable=False, default=None)
    station_id:  Mapped[int]      = mapped_column(nullable=True,  default=None)
    monster_id:  Mapped[int]      = mapped_column(nullable=True,  default=None)
    xp_gained:   Mapped[int]      = mapped_column(nullable=False, default=None)
    level_up_id: Mapped[int]      = mapped_column(nullable=True,  default=None)

class HeroLevelUpLog(Base):
    __tablename__ = "hero_level_up_logs"
    id:                Mapped[int]      = mapped_column(primary_key=True, nullable=False)
    timestamp:         Mapped[datetime] = mapped_column(nullable=False, default=None)
    hero_id:           Mapped[int]      = mapped_column(nullable=False, default=None)
    increased_ability: Mapped[str]      = mapped_column(nullable=False, default=None)

class HeroSpecialStationLog(Base):
    __tablename__ = "hero_special_station_logs"
    id:                Mapped[int]      = mapped_column(primary_key=True, nullable=False)
    station:           Mapped[str]      = mapped_column(nullable=False, default=None)
    timestamp:         Mapped[datetime] = mapped_column(nullable=False, default=None)
    hero_id:           Mapped[int]      = mapped_column(nullable=False, default=None)
    wisdom:            Mapped[int]      = mapped_column(nullable=False, default=None)
    dice:              Mapped[int]      = mapped_column(nullable=False, default=None)
    ability:           Mapped[str]      = mapped_column(nullable=True,  default=None)
    ability_plus:      Mapped[int]      = mapped_column(nullable=True, default=None)

class HeroDoorLog(Base):
    __tablename__ = "hero_door_logs"
    id:           Mapped[int]      = mapped_column(primary_key=True, nullable=False)
    timestamp:    Mapped[datetime] = mapped_column(nullable=False, default=None)
    hero_id:      Mapped[int]      = mapped_column(nullable=False, default=None)
    is_question:  Mapped[bool]     = mapped_column(nullable=True, default=None)
    is_staff:     Mapped[bool]     = mapped_column(nullable=True, default=None)
    monster_id:   Mapped[int]      = mapped_column(nullable=True, default=None)
    ability:      Mapped[str]      = mapped_column(nullable=True, default=None)
    hero_victory: Mapped[bool]     = mapped_column(nullable=True, default=None)

class FightLog(Base):
    __tablename__ = "fight_logs"
    id:               Mapped[int]      = mapped_column(primary_key=True, nullable=False)
    timestamp:        Mapped[datetime] = mapped_column(nullable=False, default=None)
    horde_hero_id:    Mapped[int]      = mapped_column(nullable=False, default=None)
    alliance_hero_id: Mapped[int]      = mapped_column(nullable=False, default=None)

    horde_health:    Mapped[int] = mapped_column(nullable=True, default=None)
    alliance_health: Mapped[int] = mapped_column(nullable=True, default=None)

    horde_inspiration:    Mapped[bool] = mapped_column(nullable=True, default=None)
    alliance_inspiration: Mapped[bool] = mapped_column(nullable=True, default=None)

    horde_know_vulnerability:    Mapped[bool] = mapped_column(nullable=True, default=None)
    alliance_know_vulnerability: Mapped[bool] = mapped_column(nullable=True, default=None)

    horde_own_vulnerability:    Mapped[bool] = mapped_column(nullable=True, default=None)
    alliance_own_vulnerability: Mapped[bool] = mapped_column(nullable=True, default=None)

    horde_use_vulnerability:    Mapped[bool] = mapped_column(nullable=True, default=None)
    alliance_use_vulnerability: Mapped[bool] = mapped_column(nullable=True, default=None)

    horde_def_vulnerability:    Mapped[bool] = mapped_column(nullable=True, default=None)
    alliance_def_vulnerability: Mapped[bool] = mapped_column(nullable=True, default=None)

    horde_dice_roll:    Mapped[int] = mapped_column(nullable=True, default=None)
    alliance_dice_roll: Mapped[int] = mapped_column(nullable=True, default=None)

    horde_victory:    Mapped[bool] = mapped_column(nullable=True, default=None)
    alliance_victory: Mapped[bool] = mapped_column(nullable=True, default=None)

class FightToUi(Base):
    __tablename__ = "fight_to_ui_table"
    id: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    
    horde_name:         Mapped[str] = mapped_column(nullable=True, default=None)
    horde_level:        Mapped[int] = mapped_column(nullable=True, default=None)
    horde_health:       Mapped[int] = mapped_column(nullable=True, default=None)
    horde_constitution: Mapped[int] = mapped_column(nullable=True, default=None)
    horde_strength:     Mapped[int] = mapped_column(nullable=True, default=None)
    horde_dexterity:    Mapped[int] = mapped_column(nullable=True, default=None)
    horde_wisdom:       Mapped[int] = mapped_column(nullable=True, default=None)
    horde_bi:           Mapped[str] = mapped_column(nullable=True, default=None)
    horde_color:        Mapped[str] = mapped_column(nullable=True, default=None)
    
    alliance_name:         Mapped[str] = mapped_column(nullable=True, default=None)
    alliance_level:        Mapped[int] = mapped_column(nullable=True, default=None)
    alliance_health:       Mapped[int] = mapped_column(nullable=True, default=None)
    alliance_constitution: Mapped[int] = mapped_column(nullable=True, default=None)
    alliance_strength:     Mapped[int] = mapped_column(nullable=True, default=None)
    alliance_dexterity:    Mapped[int] = mapped_column(nullable=True, default=None)
    alliance_wisdom:       Mapped[int] = mapped_column(nullable=True, default=None)
    alliance_bi:           Mapped[str] = mapped_column(nullable=True, default=None)
    alliance_color:        Mapped[str] = mapped_column(nullable=True, default=None)