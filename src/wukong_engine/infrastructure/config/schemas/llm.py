from typing import Any, ClassVar

from pydantic import BaseModel, StrictStr, field_validator

from wukong_engine.app.data_extraction.model.values import ExecutionMode


class LLMConfigSchema(BaseModel):
    """LLM configuration schema."""

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
        """Normalize execution mode strings to ExecutionMode members."""
        if isinstance(value, str):
            return cls._EXECUTION_MODE_ALIASES.get(value.strip().lower(), value)
        return value
