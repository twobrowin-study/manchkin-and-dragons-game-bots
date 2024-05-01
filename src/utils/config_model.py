import os
import yaml
from dotenv import load_dotenv, find_dotenv
from pydantic import (
    BaseModel,
)
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict
)

from loguru import logger

class BotConfig(BaseModel):
    token:   str
    my_name: str

class TextAndReplyKeyboard(BaseModel):
    text:    str
    buttons: list[str]

class TextAndInlineKeyboard(BaseModel):
    text:           str
    inline_buttons: list[str]

class DiceRoll(BaseModel):
    text: str

class MasterBotConfig(BotConfig):
    chat_id: int
    help:           TextAndReplyKeyboard
    start_fights:   TextAndReplyKeyboard
    fights_started: TextAndReplyKeyboard

    new_fight_started:    TextAndReplyKeyboard
    no_fight_is_possible: TextAndReplyKeyboard

    inspiration: TextAndReplyKeyboard

    vulnerability_use: TextAndReplyKeyboard
    vulnerability_def: TextAndReplyKeyboard

    horde_initiative:    DiceRoll
    alliance_initiative: DiceRoll

    horde_attack:   DiceRoll
    aliance_attack: DiceRoll

    horde_def:   DiceRoll
    aliance_def: DiceRoll

    horde_win:   TextAndReplyKeyboard
    aliance_win: TextAndReplyKeyboard

class HeroBotConfig(BotConfig):
    greeting: TextAndReplyKeyboard
    
    test:     TextAndReplyKeyboard
    answer_keyboard: list[str]

    last_test: TextAndReplyKeyboard
    tutorial_first_level: TextAndReplyKeyboard
    
    fair:  TextAndReplyKeyboard
    fight: TextAndReplyKeyboard

    hero:  TextAndReplyKeyboard
    qr: TextAndReplyKeyboard
    known_vulnerabilities: TextAndReplyKeyboard

    gained_xp: TextAndReplyKeyboard
    level_up:  TextAndInlineKeyboard

    time_to_visit_staff:  TextAndReplyKeyboard
    time_to_visit_colors: TextAndReplyKeyboard

    still_time_to_visit_staff:  TextAndReplyKeyboard
    still_time_to_visit_colors: TextAndReplyKeyboard

    ability_increase_start: TextAndReplyKeyboard
    no_awaliable_points:     TextAndReplyKeyboard
    ability_increase_end:   TextAndReplyKeyboard
    wisdom_decresed:         TextAndReplyKeyboard
    points_still_awaliable:  TextAndInlineKeyboard

    fight_start: TextAndReplyKeyboard
    tutor_fight: TextAndReplyKeyboard

class StationBotConfig(BotConfig):
    help:    TextAndReplyKeyboard
    qr:      TextAndReplyKeyboard
    success: TextAndReplyKeyboard

class DiceResult(BaseModel):
    text:    str
    hero:    str
    buttons: list[str]

class ColorBotConfig(BotConfig):
    chat_id: int
    
    help:     TextAndReplyKeyboard
    qr:       TextAndReplyKeyboard
    no_visit: TextAndReplyKeyboard
    
    dice:     DiceRoll
    
    d1:       DiceResult
    d20:      DiceResult
    d2to9:    DiceResult
    d10to14:  DiceResult
    d15plus:  DiceResult

class StaffBotConfig(BotConfig):
    chat_id: int
    
    help:     TextAndReplyKeyboard
    qr:       TextAndReplyKeyboard
    no_visit: TextAndReplyKeyboard
    visit:    TextAndReplyKeyboard
    
    dice:     DiceRoll
    
    d1:       DiceResult
    d20:      DiceResult
    d2to7:    DiceResult
    d8to10:   DiceResult
    d11to16:  DiceResult
    d17plus:  DiceResult

class GossipBotConfig(BotConfig):
    chat_id: int
    
    help:     TextAndReplyKeyboard
    qr:       TextAndReplyKeyboard
    no_visit: TextAndReplyKeyboard
    visit:    TextAndReplyKeyboard

    counterpart_hero_known_vulnerability: TextAndReplyKeyboard
    no_new_gossip:    TextAndReplyKeyboard
    all_already_know: TextAndReplyKeyboard
    
    dice:     DiceRoll
    
    d1:      DiceResult
    d20:     DiceResult
    d2to10:  DiceResult
    d11to16: DiceResult
    d17plus: DiceResult

class DoorsBotConfig(BotConfig):
    chat_id: int
    question_xp: int
    
    help:  TextAndReplyKeyboard
    qr:    TextAndReplyKeyboard
    visit: TextAndReplyKeyboard

    staff: TextAndReplyKeyboard

    question:  TextAndReplyKeyboard
    correct:   TextAndReplyKeyboard
    incorrect: TextAndReplyKeyboard

    monster_qr: TextAndReplyKeyboard
    
    hero:    TextAndReplyKeyboard
    monster: TextAndReplyKeyboard
    
    ability_hero_dice:        DiceRoll
    hero_result_monster_dice: DiceRoll
    
    d1:      DiceResult
    d20:     DiceResult
    victory: DiceResult
    defeat:  DiceResult

class FightConfig(BaseModel):
    alliance_chat_id: int
    horde_chat_id:    int

    introduction: str

    inspiration: str
    
    vulnerability_use:    str
    vulnerability_def:    str
    vulnerability_result: str

    d1:  str
    d20: str

    initiative_win:  str
    initiative_loose: str

    atack_loose: str
    atack_win:   str

    def_loose: str
    def_win:   str

    defeat:  str
    victory: str

class I18n(BaseModel):
    help:   str
    cancel: str
    qr_processing: str

class ConfigYaml(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter='__')

    pg_user:     str
    pg_password: str
    
    minio_root_user:     str
    minio_root_password: str
    minio_secure: bool
    minio_host:   str
    minio_bucket: str

    error_message: str

    master:  MasterBotConfig
    hero:    HeroBotConfig
    station: StationBotConfig
    color:   ColorBotConfig
    staff:   StaffBotConfig
    gossip:  GossipBotConfig
    doors:   DoorsBotConfig

    fight: FightConfig

    buttons_fun_to_i18n: dict[str, str]
    buttons_i18n_to_fun: dict[str, str]

    i18n: I18n
    
def create_config() -> ConfigYaml:
    """
    Создание конфига из файла и переменных окружения
    """

    load_dotenv(find_dotenv())
    GAME_HOME = os.getenv('GAME_HOME')

    if not GAME_HOME:
        GAME_HOME = os.getcwd()

    with open(f"{GAME_HOME}/config/config.yaml", "r") as stream:
        full_config = yaml.safe_load(stream)

    if not full_config:
        full_config = {}
    
    full_config['minio_secure'] = False
    if os.getenv('MINIO_CERTDIR'):
        full_config['minio_secure'] = True

    buttons_fun_to_i18n: dict[str, str] = full_config['buttons_fun_to_i18n']
    full_config['buttons_i18n_to_fun'] = {
        val: key for key,val in buttons_fun_to_i18n.items()
    }

    config_obj = ConfigYaml(**full_config)
    
    logger.info(f"\n{config_obj.model_dump_json(indent=4)}")

    return config_obj
