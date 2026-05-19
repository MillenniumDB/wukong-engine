from pydantic import BaseModel, StrictInt


class ChunkingConfigSchema(BaseModel):
    """Chunking configuration schema."""

    target_tokens: StrictInt | None = None
    max_tokens: StrictInt | None = None
    overlap_tokens: StrictInt | None = None
