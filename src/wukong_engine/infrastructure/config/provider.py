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
        """Get the application configuration."""
        config = load_toml(path)
        schema = ApplicationConfigSchema.model_validate(config)
        app_config = ApplicationConfigMapper().map_configuration(schema)
        logger.info(f'Configuration obtained successfully from "{path}"\n\n{app_config}')
        return app_config
