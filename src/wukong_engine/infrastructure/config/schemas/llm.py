from pydantic import BaseModel, StrictBool, StrictStr


class LLMConfigSchema(BaseModel):
    """LLM configuration schema."""

    model: StrictStr | None = None
    strict_support: StrictBool | None = None
