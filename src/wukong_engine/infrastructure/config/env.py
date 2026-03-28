import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class EnvConfig:
    """Configuration for environment variables."""

    openai_api_key: str


def load_env_config() -> EnvConfig:
    """Load environment variables."""
    load_dotenv('.env', override=False)
    return EnvConfig(openai_api_key=_require('OPENAI_API_KEY'))


def _require(key: str) -> str:
    value = os.getenv(key)
    if value is None or value.strip() == '':
        raise RuntimeError(f'Missing required environment variable: {key}')
    return value
