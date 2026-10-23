"""Schema for the LLM configuration section."""

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, StrictInt, StrictStr, field_validator

from wukong_engine.app.data_extraction.model.values import ExecutionMode
from wukong_engine.app.llm.elements.values import ReasoningEffort


class LLMConfigSchema(BaseModel):
    """LLM configuration schema.

    Attributes:
        model: Name of the LLM to use, case-insensitive. If None, the model default is used.
        execution_mode: Execution mode for extraction jobs. Case-insensitive aliases (e.g. ``realtime``, ``sync``,
            ``batch``, ``async``) are accepted. If None, the model default is used.
        max_concurrency: Maximum number of concurrent LLM requests. If None, the model default is used.
        reasoning_effort: Generalized reasoning effort level overriding the LLM model's default (e.g. ``none``,
            ``low``, ``extreme``), case-insensitive. If None, the LLM model's default is used.
    """

    model_config = ConfigDict(extra='forbid')

    model: StrictStr | None = None
    execution_mode: ExecutionMode | None = None
    max_concurrency: StrictInt | None = None
    reasoning_effort: ReasoningEffort | None = None

    # Mapping of various string representations to ExecutionMode members
    _EXECUTION_MODE_ALIASES: ClassVar[dict[str, ExecutionMode]] = {
        'realtime': ExecutionMode.REALTIME,
        'real_time': ExecutionMode.REALTIME,
        'real-time': ExecutionMode.REALTIME,
        'sync': ExecutionMode.REALTIME,
        'synchronous': ExecutionMode.REALTIME,
        'immediate': ExecutionMode.REALTIME,
        'batch': ExecutionMode.BATCH,
        'batched': ExecutionMode.BATCH,
        'async': ExecutionMode.BATCH,
        'asynchronous': ExecutionMode.BATCH,
        'queue': ExecutionMode.BATCH,
        'queued': ExecutionMode.BATCH,
        'deferred': ExecutionMode.BATCH,
    }

    @field_validator('execution_mode', mode='before')
    @classmethod
    def normalize_execution_mode(cls, value: Any) -> Any:
        """Normalize execution mode strings to ExecutionMode members.

        Args:
            value: Raw ``execution_mode`` value from the configuration.

        Returns:
            The matching ExecutionMode member for a known alias, or the value unchanged otherwise, for pydantic to
            validate.
        """
        if isinstance(value, str):
            return cls._EXECUTION_MODE_ALIASES.get(value.strip().lower(), value)
        return value

    @field_validator('model', mode='before')
    @classmethod
    def normalize_model(cls, value: Any) -> Any:
        """Normalize model names, rejecting empty ones.

        Args:
            value: Raw ``model`` value from the configuration.

        Returns:
            The trimmed, lowercased name for a string, or the value unchanged otherwise, for pydantic to validate.

        Raises:
            ValueError: If the name is empty, which is rejected rather than read as unset so that a mistake doesn't
                silently run the default model.
        """
        if isinstance(value, str):
            value = value.strip().lower()
            if not value:
                raise ValueError('must not be empty; remove the key to use the default model')
        return value

    @field_validator('reasoning_effort', mode='before')
    @classmethod
    def normalize_reasoning_effort(cls, value: Any) -> Any:
        """Normalize reasoning effort strings.

        Args:
            value: Raw ``reasoning_effort`` value from the configuration.

        Returns:
            The trimmed, lowercased level for a string, or the value unchanged otherwise, for pydantic to validate.
        """
        if isinstance(value, str):
            return value.strip().lower()
        return value
