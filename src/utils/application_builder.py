from telegram.ext import ApplicationBuilder

from utils.application import GameApplication
from utils.config_model import create_config, BotConfig

class GameApplicationBuilder(ApplicationBuilder):
    def __init__(self):
        super().__init__()
        self._application_class = GameApplication
    
    def name(self, name: str):
        self._name   = name
        self._config = create_config()

        self._bot_config: BotConfig = getattr(self._config, self._name)
        
        self._token = self._bot_config.token
        self._application_kwargs = {
            'name':       self._name,
            'config':     self._config,
            'bot_config': self._bot_config
        }
        return self