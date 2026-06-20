from enum import Enum


class PipelineCheckpoint(Enum):
    """Pipeline key stages for checkpointing and resuming pipelines.

    Attributes:
        DOCUMENTS_INGESTED: All documents/chunks have been ingested.
        PENDING_ENTITY_EXTRACTIONS_MATERIALIZED: Pending entity extractions have been materialized.
        ENTITIES_EXTRACTED: All entities have been extracted.
        PENDING_RELATIONSHIP_EXTRACTIONS_MATERIALIZED: Pending relationship extractions have been materialized.
        RELATIONSHIPS_EXTRACTED: All relationships have been extracted.
    """

    DOCUMENTS_INGESTED = 'DOCUMENTS_INGESTED'
    PENDING_ENTITY_EXTRACTIONS_MATERIALIZED = 'PENDING_ENTITY_EXTRACTIONS_MATERIALIZED'
    ENTITIES_EXTRACTED = 'ENTITIES_EXTRACTED'
    PENDING_RELATIONSHIP_EXTRACTIONS_MATERIALIZED = 'PENDING_RELATIONSHIP_EXTRACTIONS_MATERIALIZED'
    RELATIONSHIPS_EXTRACTED = 'RELATIONSHIPS_EXTRACTED'
