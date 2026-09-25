"""Schema for the LLM configuration section."""

from typing import Any, ClassVar

from pydantic import BaseModel, StrictStr, field_validator

from wukong_engine.app.data_extraction.model.values import ExecutionMode


class LLMConfigSchema(BaseModel):
    """LLM configuration schema.

    Attributes:
        model: Name of the LLM to use. If None, the model default is used.
        execution_mode: Execution mode for extraction jobs. Case-insensitive aliases (e.g. ``realtime``, ``sync``,
            ``batch``, ``async``) are accepted. If None, the model default is used.
        max_concurrency: Maximum number of concurrent LLM requests. If None, the model default is used.
    """

    model: StrictStr | None = None
    execution_mode: ExecutionMode | None = None
    max_concurrency: int | None = None

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
