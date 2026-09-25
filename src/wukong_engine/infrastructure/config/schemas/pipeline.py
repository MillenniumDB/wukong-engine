"""Schema for the pipeline configuration section."""

from pydantic import BaseModel, StrictBool


class PipelineConfigSchema(BaseModel):
    """Pipeline configuration schema.

    Attributes:
        ingest_documents: Whether the document ingestion step runs. If None, the model default is used.
        extract_entities: Whether the entity extraction step runs. If None, the model default is used.
        extract_relationships: Whether the relationship extraction step runs. If None, the model default is used.
        export_knowledge: Whether the knowledge export step runs. If None, the model default is used.
    """

    ingest_documents: StrictBool | None = None
    extract_entities: StrictBool | None = None
    extract_relationships: StrictBool | None = None
    export_knowledge: StrictBool | None = None
