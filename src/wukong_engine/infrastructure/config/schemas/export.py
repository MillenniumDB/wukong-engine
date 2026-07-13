from typing import Any, ClassVar

from pydantic import BaseModel, field_validator

from wukong_engine.app.knowledge_export.model.values import KnowledgeExportFormat


class ExportConfigSchema(BaseModel):
    """Export configuration schema."""

    format: KnowledgeExportFormat | None = None

    # Mapping of various string representations to KnowledgeExportFormat members
    _EXPORT_FORMAT_ALIASES: ClassVar[dict[str, KnowledgeExportFormat]] = {
        'json': KnowledgeExportFormat.JSON,
        'mdb': KnowledgeExportFormat.MDB,
        'millenniumdb': KnowledgeExportFormat.MDB,
        'neo4j': KnowledgeExportFormat.NEO4J,
    }

    @field_validator('format', mode='before')
    @classmethod
    def normalize_format(cls, value: Any) -> Any:
        """Normalize format strings to KnowledgeExportFormat members."""
        if isinstance(value, str):
            return cls._EXPORT_FORMAT_ALIASES.get(value.strip().lower(), value)
        return value
