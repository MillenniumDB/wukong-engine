"""Implements the configuration manager class.

As
"""

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
CONFIG_PATH = Path('./config/config.toml')


class Config(Singleton):
    """The central configuration manager for the WUKONG engine.

    Loads and validates the engine configuration,
    exposing the resulting settings as attributes and access methods.
    The configuration is loaded once and is assumed to be immutable for the duration of the program.
    """

    def __init__(self) -> None:
        """Initialize the configuration manager.

        Loads the configuration and processes it to store each relevant component.
        """
        # Components of the configuration
        self._pipeline = {}
        self._parameters = {}
        self._env = {}

        # Initialize the configuration
        self._load_config(CONFIG_PATH)

    def _load_config(self, config_path: Path) -> None:
        """Load the configuration from a TOML file and environment variables, making sure it has a valid format.

        Args:
            config_path: The path to the TOML configuration file.

        Raises:
            FileNotFoundError: If the configuration file does not exist.
            ValueError: If the configuration file has an invalid structure or if required environment variables are missing.
        """
        # Check if the config file exists
        if not config_path.exists():
            raise FileNotFoundError(f'Configuration file "{config_path}" not found')

        # Load the configuration
        try:
            config = tomllib.loads(config_path.read_text(encoding='utf-8'))
        except tomllib.TOMLDecodeError as error:
            raise ValueError(f'Invalid structure for the configuration in "{config_path}"') from error

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
        """Check whether a specific pipeline step is enabled.

        Args:
            step: The name of the pipeline step to check.

        Returns:
            True if the step is enabled, False otherwise.
        """
        return bool(self._pipeline.get(step, False))

    def get(self, key: str, default: Any = None) -> Any:
        """Get a specific configuration parameter value.

        Args:
            key: The name of the configuration parameter to retrieve.
            default: The default value to return if the parameter is not found.

        Returns:
            The value of the configuration parameter if it exists, otherwise the default value.
        """
        return self._parameters.get(key, default)

    def get_env(self, key: str, default: Any = None) -> Any:
        """Get a specific environment variable value.

        Args:
            key: The name of the environment variable to retrieve.
            default: The default value to return if the environment variable is not found.

        Returns:
            The value of the environment variable if it exists, otherwise the default value.
        """
        return self._env.get(key, default)
