from typing import Any, ClassVar

from pydantic import BaseModel, StrictBool, field_validator

from wukong_engine.app.config.pipeline import RunMode


class PipelineConfigSchema(BaseModel):
    """Pipeline configuration schema."""

    run_mode: RunMode = RunMode.EXPERIMENTAL
    extract_entities: StrictBool = True
    extract_relationships: StrictBool = True
    export_graph: StrictBool = True

    # Mapping of various string representations to RunMode members
    _RUN_MODE_ALIASES: ClassVar[dict[str, RunMode]] = {
        'experimental': RunMode.EXPERIMENTAL,
        'development': RunMode.EXPERIMENTAL,
        'dev': RunMode.EXPERIMENTAL,
        'testing': RunMode.EXPERIMENTAL,
        'test': RunMode.EXPERIMENTAL,
        'sandbox': RunMode.EXPERIMENTAL,
        'production': RunMode.PRODUCTION,
        'prod': RunMode.PRODUCTION,
        'stable': RunMode.PRODUCTION,
        'persistent': RunMode.PRODUCTION,
        'incremental': RunMode.PRODUCTION,
    }

    @field_validator('run_mode', mode='before')
    @classmethod
    def normalize_run_mode(cls, value: Any) -> Any:
        """Normalize run mode strings to RunMode members."""
        if isinstance(value, str):
            return cls._RUN_MODE_ALIASES.get(value, value)
        return value
