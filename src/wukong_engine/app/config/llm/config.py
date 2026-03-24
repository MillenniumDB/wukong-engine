import logging
from dataclasses import dataclass

from .model import LLM
from .provider import LLMProvider
from .registry import LLMRegistry

# Logging
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMConfig:
    """LLM configuration."""

    model: LLM
    provider: LLMProvider = LLMProvider.OPENAI
    strict: bool = True

    def __str__(self) -> str:
        """User-friendly string representation of the LLM configuration."""
        return f'Model: {self.model.name} ({self.provider.value})'

    def __post_init__(self) -> None:
        """Validate LLM configuration invariants."""
        self._validate_model()

    def _validate_model(self) -> None:
        if not LLMRegistry.is_supported_model(self.provider, self.model.name):
            if self.strict:
                supported_models = ', '.join(LLMRegistry.get_supported_models(self.provider))
                raise ValueError(
                    f'Unsupported LLM model "{self.model.name}" for provider "{self.provider.value}". '
                    f'Supported models from {self.provider.value}: {supported_models}',
                )

            # Log a warning but allow unsupported models to be used in non-strict mode
            logger.warning(
                f'LLM model "{self.model.name}" is not officially supported for provider "{self.provider.value}". '
                f'Proceeding with caution.',
            )
