"""LLM client factory configured from the environment."""

from wukong_engine.app.llm.elements import LLMClient, LLMClientFactory
from wukong_engine.app.llm.exceptions import LLMConfigurationError
from wukong_engine.app.llm.model import LLM, LLMRegistry
from wukong_engine.app.llm.model.values import LLMProvider
from wukong_engine.infrastructure.config import load_env_config
from wukong_engine.infrastructure.llm.anthropic import AnthropicClient, AnthropicConfig
from wukong_engine.infrastructure.llm.openai import OpenAIClient, OpenAIConfig


class EnvLLMClientFactory(LLMClientFactory):
    """Factory of LLM clients authenticated with the API key of each provider found in the environment.

    The configured model's client is created on initialization, so that a missing API key of its provider aborts the
    run. The clients of other providers are created once first requested, with their provider's default model, which
    they never use since they only manage the batches already submitted to them. Without a configured model, as when
    only managing batches, every client is created once first requested.
    """

    def __init__(self, model: LLM | None = None) -> None:
        """Initialize the factory with the client of the configured model, if any.

        Args:
            model: Configured model, used by the client of its provider. None if no model is configured.

        Raises:
            RuntimeError: If the API key of the model's provider is missing or blank.
            ValueError: If the provider is not supported or its client cannot be configured for the model.
        """
        self._clients: dict[LLMProvider, LLMClient] = {}
        if model is not None:
            api_key = load_env_config(model.provider).llm_api_key
            self._clients[model.provider] = self._create_client(model, api_key)

    @staticmethod
    def _create_client(model: LLM, api_key: str) -> LLMClient:
        """Create an LLM client of the model's provider.

        Args:
            model: Model used by the client.
            api_key: API key of the model's provider.

        Returns:
            The LLM client for the model's provider.

        Raises:
            ValueError: If the provider is not supported or its client cannot be configured for the model.
        """
        match model.provider:
            case LLMProvider.OPENAI:
                return OpenAIClient(config=OpenAIConfig(api_key=api_key, model=model))
            case LLMProvider.ANTHROPIC:
                return AnthropicClient(config=AnthropicConfig(api_key=api_key, model=model))
            case _:
                raise ValueError(f'Unsupported LLM provider: {model.provider}')

    def get_client(self, provider: LLMProvider) -> LLMClient:
        """Get the client of a provider, creating it the first time it is requested.

        Args:
            provider: Provider whose client is returned.

        Returns:
            The LLM client of the provider.

        Raises:
            LLMConfigurationError: If the API key of the provider is missing or blank, or its client cannot be
                configured.
        """
        client = self._clients.get(provider)
        if client is None:
            try:
                api_key = load_env_config(provider).llm_api_key
                client = self._create_client(LLMRegistry.default_model(provider), api_key)
            except (RuntimeError, ValueError) as exc:
                raise LLMConfigurationError(str(exc)) from exc
            self._clients[provider] = client
        return client
