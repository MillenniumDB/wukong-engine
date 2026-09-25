"""LLM configuration."""

import logging
from dataclasses import dataclass, field

from wukong_engine.app.data_extraction.model.values import ExecutionMode
from wukong_engine.app.llm.model import LLM, LLMRegistry

# Logging
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class LLMConfig:
    """LLM configuration.

    Attributes:
        model: LLM used for extraction. Defaults to the registry's default model.
        execution_mode: Whether extraction jobs run in realtime or through the provider's batch API.
        max_concurrency: Maximum number of concurrent LLM requests.
    """

    model: LLM = field(default_factory=LLMRegistry.default_model)
    execution_mode: ExecutionMode = ExecutionMode.REALTIME
    max_concurrency: int = 5

    def __str__(self) -> str:
        """User-friendly string representation of the LLM configuration."""
        return (
            f'Model: {self.model}\nExecution Mode: {self.execution_mode.value}\nMax Concurrency: {self.max_concurrency}'
        )

    def __post_init__(self) -> None:
        """Validate LLM configuration invariants.

        Raises:
            ValueError: If the model is not supported or ``max_concurrency`` is less than 1.
        """
        self._validate_model()
        self._validate_concurrency()

    def _validate_model(self) -> None:
        """Validate that the specified model is supported.

        Raises:
            ValueError: If the model is not registered as supported for its provider.
        """
        if not LLMRegistry.is_supported_model(self.model):
            supported_models = ', '.join(LLMRegistry.supported_models(self.model.provider))
            raise ValueError(
                f'Unsupported LLM model "{self.model.name}" for provider "{self.model.provider.value}". '
                f'Supported models from {self.model.provider.value}: {supported_models}',
            )

    def _validate_concurrency(self) -> None:
        """Validate that the max concurrency is a positive integer.

        Raises:
            ValueError: If ``max_concurrency`` is less than 1.
        """
        if self.max_concurrency < 1:
            raise ValueError('Max concurrency must be at least 1.')
