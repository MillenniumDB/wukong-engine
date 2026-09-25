"""Environment variable configuration."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class EnvConfig:
    """Configuration for environment variables.

    Attributes:
        openai_api_key: API key used to authenticate with OpenAI, read from ``OPENAI_API_KEY``.
    """

    openai_api_key: str


def load_env_config() -> EnvConfig:
    """Load environment variables.

    Variables from a ``.env`` file in the current working directory are loaded first, without overriding variables
    already set in the environment.

    Returns:
        The environment configuration.

    Raises:
        RuntimeError: If a required environment variable is missing or blank.
    """
    load_dotenv('.env', override=False)
    return EnvConfig(openai_api_key=_require('OPENAI_API_KEY'))


def _require(key: str) -> str:
    """Return the value of a required environment variable.

    Args:
        key: Name of the environment variable.

    Returns:
        The variable's value.

    Raises:
        RuntimeError: If the variable is unset or blank.
    """
    value = os.getenv(key)
    if value is None or value.strip() == '':
        raise RuntimeError(f'Missing required environment variable: {key}')
    return value
