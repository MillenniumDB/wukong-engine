import logging
import os
import tomllib
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from wukong_engine.utils.patterns import Singleton

# Logging
logger = logging.getLogger(__name__)

# Paths
CONFIG_PATH = Path('./config.toml')


class Config(Singleton):
    """
    Configuration class for the WUKONG engine.
    """

    def __init__(self, config_path: Path = CONFIG_PATH) -> None:
        # Components of the configuration
        self._pipeline = {}
        self._parameters = {}
        self._env = {}

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
        except tomllib.TOMLDecodeError as error:
            raise ValueError(f'Invalid structure for the Configuration in "{config_path}"') from error

        # Store the valid configuration
        self._pipeline = config['pipeline']
        self._parameters = config['parameters']

        # Load environment variables
        load_dotenv('.env')  # Load from .env file (for development only)
        self._env['OPENAI_API_KEY'] = os.getenv('OPENAI_API_KEY')

        # Validate that all required environment variables are set
        if any(value is None for value in self._env.values()):
            raise ValueError('Missing required environment variables')
        logger.info(f'Configuration loaded successfully from: "{config_path}"')

    def is_enabled(self, step: str) -> bool:
        """
        Check if a specific step in the pipeline is enabled.
        """
        return bool(self._pipeline.get(step, False))

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a specific configuration parameter.
        """
        return self._parameters.get(key, default)

    def get_env(self, key: str, default: Any = None) -> Any:
        """
        Get a specific environment variable value.
        """
        return self._env.get(key, default)
