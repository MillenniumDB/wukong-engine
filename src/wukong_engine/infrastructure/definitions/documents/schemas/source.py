from typing import Any, ClassVar

from pydantic import BaseModel, StrictStr, field_validator

from wukong_engine.core.documents.model.values import DocumentSourceMode


class DocumentSourceSchema(BaseModel):
    """Schema-level representation of a document source."""

    root: StrictStr
    mode: DocumentSourceMode

    # Mapping of various string representations to DocumentSourceMode members
    _SOURCE_MODE_ALIASES: ClassVar[dict[str, DocumentSourceMode]] = {
        'file': DocumentSourceMode.FILE,
        'document': DocumentSourceMode.FILE,
        'single': DocumentSourceMode.FILE,
        'directory': DocumentSourceMode.DIRECTORY,
        'dir': DocumentSourceMode.DIRECTORY,
        'folder': DocumentSourceMode.DIRECTORY,
        'recursive': DocumentSourceMode.RECURSIVE,
        'nested': DocumentSourceMode.RECURSIVE,
        'deep': DocumentSourceMode.RECURSIVE,
    }

    @field_validator('mode', mode='before')
    @classmethod
    def normalize_mode(cls, value: Any) -> Any:
        """Normalize source mode strings to DocumentSourceMode members."""
        if isinstance(value, str):
            return cls._SOURCE_MODE_ALIASES.get(value.strip().lower(), value)
        return value

    @field_validator('root')
    @classmethod
    def validate_root(cls, value: str) -> str:
        """Validate that the root is well-formed."""
        if not value.strip():
            raise ValueError('Root must not be empty.')
        return value
