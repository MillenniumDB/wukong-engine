import logging
import os
import tomllib
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

### Environment Variables ###

# Load from .env file (for development only)
load_dotenv('.env')

# Get environment variables
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

### Configuration ###

# Logging
logger = logging.getLogger(__name__)

# Paths
CONFIG_PATH = Path('./config.toml')


class Singleton(type):
    """
    Class to adapt the Singleton design pattern.
    """

    _instances = {}

    def __call__(cls, *args, **kwargs):
        # If a specific class has already been instantiated before, return the existing instance
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class Config(metaclass=Singleton):
    """
    Configuration class for the WUKONG engine.
    """

    def __init__(self, config_path: Path = CONFIG_PATH) -> None:
        # Components of the configuration
        self._pipeline = {}
        self._parameters = {}

        # Initialize the configuration
        self._load_config(config_path)

    def _load_config(self, config_path: Path) -> None:
        """
        Load configuration from a JSON file.
        """
        # Check if the config file exists
        if not config_path.exists():
            raise FileNotFoundError(f'Configuration file "{config_path}" not found')

        # Load the configuration
        try:
            config = tomllib.loads(config_path.read_text(encoding='utf-8'))
        except tomllib.TOMLDecodeError:
            raise ValueError(f'Invalid structure for the Configuration in "{config_path}"')

        # Store the valid configuration
        self._pipeline = config['pipeline']
        self._parameters = config['parameters']
        logger.info(f'Configuration loaded successfully from: "{config_path}"')

    def is_enabled(self, step: str) -> bool:
        """
        Check if a specific step in the pipeline is enabled.
        """
        return bool(self._pipeline.get(step, False))

    def get(self, key: str, default=None) -> Any:
        """
        Get a specific configuration parameter.
        """
        return self._parameters.get(key, default)
