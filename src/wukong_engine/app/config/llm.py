import logging
from dataclasses import dataclass, field

from wukong_engine.app.llm.model import LLM, LLMRegistry

# Logging
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMConfig:
    """LLM configuration."""

    model: LLM = field(default_factory=LLMRegistry.default_model)
    strict_support: bool = True
    max_concurrency: int = 5

    def __str__(self) -> str:
        """User-friendly string representation of the LLM configuration."""
        return f'Model: {self.model}\nMax Concurrency: {self.max_concurrency}'

    def __post_init__(self) -> None:
        """Validate LLM configuration invariants."""
        self._validate_model()
        self._validate_concurrency()

    def _validate_model(self) -> None:
        """Validate that the specified model is supported."""
        if not LLMRegistry.is_supported_model(self.model):
            if self.strict_support:
                supported_models = ', '.join(LLMRegistry.supported_models(self.model.provider))
                raise ValueError(
                    f'Unsupported LLM model "{self.model.name}" for provider "{self.model.provider.value}". '
                    f'Supported models from {self.model.provider.value}: {supported_models}',
                )

            # Log a warning but allow unsupported models to be used in non-strict mode
            logger.warning(
                f'LLM model "{self.model.name}" is not officially supported for provider "{self.model.provider.value}". '
                f'Proceeding with caution.',
            )

    def _validate_concurrency(self) -> None:
        """Validate that the max concurrency is a positive integer."""
        if self.max_concurrency < 1:
            raise ValueError('Max concurrency must be at least 1.')
