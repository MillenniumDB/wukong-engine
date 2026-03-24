from pydantic import BaseModel, StrictBool, StrictStr


class LLMConfigSchema(BaseModel):
    """LLM configuration schema."""

    model: StrictStr
    strict: StrictBool = True
    # api_key: str | None = None
