"""Environment variable configuration."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

from wukong_engine.app.llm.model.values import LLMProvider

# Environment variable holding the API key of each LLM provider
_API_KEY_VARIABLES: dict[LLMProvider, str] = {
    LLMProvider.OPENAI: 'OPENAI_API_KEY',
    LLMProvider.ANTHROPIC: 'ANTHROPIC_API_KEY',
}


@dataclass(frozen=True, slots=True)
class EnvConfig:
    """Configuration for environment variables.

    Attributes:
        llm_api_key: API key used to authenticate with the configured LLM provider, read from ``OPENAI_API_KEY`` or
            ``ANTHROPIC_API_KEY``.
    """

    llm_api_key: str


def load_env_config(llm_provider: LLMProvider) -> EnvConfig:
    """Load environment variables.

    Variables from a ``.env`` file in the current working directory are loaded first, without overriding variables
    already set in the environment.

    Args:
        llm_provider: LLM provider whose API key is required.

    Returns:
        The environment configuration.

    Raises:
        RuntimeError: If a required environment variable is missing or blank.
    """
    load_dotenv('.env', override=False)
    return EnvConfig(llm_api_key=_require(_API_KEY_VARIABLES[llm_provider]))


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
