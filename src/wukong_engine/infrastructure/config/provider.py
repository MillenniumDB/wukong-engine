"""Provider that loads the application configuration from a TOML file."""

import logging
from pathlib import Path

from wukong_engine.app.config import ApplicationConfig

from .mapper import ApplicationConfigMapper
from .schemas import ApplicationConfigSchema
from .toml_loader import load_toml

# Logging
logger = logging.getLogger(__name__)


class ConfigProvider:
    """Provider for application configuration."""

    def get(self, path: Path) -> ApplicationConfig:
        """Get the application configuration.

        Args:
            path: Path to the TOML configuration file.

        Returns:
            The validated application configuration.

        Raises:
            FileNotFoundError: If the configuration file doesn't exist.
            ValueError: If the file cannot be read or parsed, or the configuration is invalid.
        """
        config = load_toml(path)
        schema = ApplicationConfigSchema.model_validate(config)
        app_config = ApplicationConfigMapper().map_configuration(schema)
        logger.info(f'Configuration obtained successfully from "{path}"\n\n{app_config}')
        return app_config
