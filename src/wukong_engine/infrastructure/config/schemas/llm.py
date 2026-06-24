from pydantic import BaseModel, StrictStr


# TODO: Processing Mode
class LLMConfigSchema(BaseModel):
    """LLM configuration schema."""

    model: StrictStr | None = None
    processing_mode: StrictStr | None = None
    max_concurrency: int | None = None
