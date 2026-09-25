"""Schema for document source definitions."""

from typing import Any, ClassVar

from pydantic import BaseModel, StrictStr, field_validator

from wukong_engine.core.documents.model.values import DocumentSourceMode


class DocumentSourceSchema(BaseModel):
    """Schema-level representation of a document source.

    Attributes:
        root: Path to the source file or directory, relative to the data directory or absolute.
        mode: How the root is expanded into documents (single file, directory, or recursive directory).
    """

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
        """Normalize source mode strings to DocumentSourceMode members.

        Args:
            value: Raw mode value; strings are matched case-insensitively against known aliases.

        Returns:
            The matching DocumentSourceMode member, or the value unchanged if it isn't a known alias.
        """
        if isinstance(value, str):
            return cls._SOURCE_MODE_ALIASES.get(value.strip().lower(), value)
        return value

    @field_validator('root')
    @classmethod
    def validate_root(cls, value: str) -> str:
        """Validate that the root is well-formed.

        Args:
            value: Raw source root.

        Returns:
            The root, unchanged.

        Raises:
            ValueError: If the root is empty or only whitespace.
        """
        if not value.strip():
            raise ValueError('Root must not be empty.')
        return value
