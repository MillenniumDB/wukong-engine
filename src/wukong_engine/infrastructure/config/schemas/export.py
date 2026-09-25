"""Schema for the export configuration section."""

from typing import Any, ClassVar

from pydantic import BaseModel, field_validator

from wukong_engine.app.knowledge_export.model.values import KnowledgeExportFormat


class ExportConfigSchema(BaseModel):
    """Export configuration schema.

    Attributes:
        format: Knowledge export format. Case-insensitive aliases (``mdb``, ``millenniumdb``, ``neo4j``) are
            accepted. If None, the model default is used.
    """

    format: KnowledgeExportFormat | None = None

    # Mapping of various string representations to KnowledgeExportFormat members
    _EXPORT_FORMAT_ALIASES: ClassVar[dict[str, KnowledgeExportFormat]] = {
        'mdb': KnowledgeExportFormat.MDB,
        'millenniumdb': KnowledgeExportFormat.MDB,
        'neo4j': KnowledgeExportFormat.NEO4J,
    }

    @field_validator('format', mode='before')
    @classmethod
    def normalize_format(cls, value: Any) -> Any:
        """Normalize format strings to KnowledgeExportFormat members.

        Args:
            value: Raw ``format`` value from the configuration.

        Returns:
            The matching KnowledgeExportFormat member for a known alias, or the value unchanged otherwise, for
            pydantic to validate.
        """
        if isinstance(value, str):
            return cls._EXPORT_FORMAT_ALIASES.get(value.strip().lower(), value)
        return value
