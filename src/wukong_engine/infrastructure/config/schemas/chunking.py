"""Schema for the chunking configuration section."""

from pydantic import BaseModel, StrictInt


class ChunkingConfigSchema(BaseModel):
    """Chunking configuration schema.

    Attributes:
        target_tokens: Target size of each chunk, in tokens. If None, the model default is used.
        overlap_tokens: Tokens shared between consecutive chunks. If None, it is derived from ``target_tokens``.
    """

    target_tokens: StrictInt | None = None
    overlap_tokens: StrictInt | None = None
