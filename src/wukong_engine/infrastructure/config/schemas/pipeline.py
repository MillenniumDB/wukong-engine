from pydantic import BaseModel, StrictBool


class PipelineConfigSchema(BaseModel):
    """Pipeline configuration schema."""

    ingest_documents: StrictBool | None = None
    extract_entities: StrictBool | None = None
    extract_relationships: StrictBool | None = None
    export_knowledge: StrictBool | None = None
