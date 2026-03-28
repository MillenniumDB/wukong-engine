from pydantic import BaseModel, StrictBool, StrictStr


class LLMConfigSchema(BaseModel):
    """LLM configuration schema."""

    model: StrictStr
    strict: StrictBool = True
