from enum import Enum

from .checkpoint import PipelineCheckpoint


class PipelineStep(Enum):
    """Pipeline steps used by the engine.

    Attributes:
        INGEST_DOCUMENTS: Ingest documents into the system.
        EXTRACT_ENTITIES: Extract entities from documents.
        EXTRACT_RELATIONSHIPS: Extract relationships between entities.
        EXPORT_KNOWLEDGE: Export the extracted knowledge.
    """

    INGEST_DOCUMENTS = 'INGEST_DOCUMENTS'
    EXTRACT_ENTITIES = 'EXTRACT_ENTITIES'
    EXTRACT_RELATIONSHIPS = 'EXTRACT_RELATIONSHIPS'
    EXPORT_KNOWLEDGE = 'EXPORT_KNOWLEDGE'

    @property
    def depends_on(self) -> set[PipelineStep]:
        """Steps that must be completed before this pipeline step can be executed."""
        return STEP_DEPENDENCIES.get(self, set())

    @property
    def is_required_by(self) -> set[PipelineStep]:
        """Steps that depend on this pipeline step being completed first."""
        return {step for step, dependencies in STEP_DEPENDENCIES.items() if self in dependencies}

    @property
    def checkpoints(self) -> set[PipelineCheckpoint]:
        """Checkpoints associated with this pipeline step."""
        return STEP_CHECKPOINTS.get(self, set())


# Mapping of pipeline steps to the steps that must be completed before they can be executed
STEP_DEPENDENCIES: dict[PipelineStep, set[PipelineStep]] = {
    PipelineStep.INGEST_DOCUMENTS: set(),
    PipelineStep.EXTRACT_ENTITIES: {PipelineStep.INGEST_DOCUMENTS},
    PipelineStep.EXTRACT_RELATIONSHIPS: {PipelineStep.INGEST_DOCUMENTS, PipelineStep.EXTRACT_ENTITIES},
    PipelineStep.EXPORT_KNOWLEDGE: {
        PipelineStep.INGEST_DOCUMENTS,
        PipelineStep.EXTRACT_ENTITIES,
        PipelineStep.EXTRACT_RELATIONSHIPS,
    },
}

# Mapping of pipeline steps to their associated checkpoints
STEP_CHECKPOINTS: dict[PipelineStep, set[PipelineCheckpoint]] = {
    PipelineStep.INGEST_DOCUMENTS: {PipelineCheckpoint.DOCUMENTS_INGESTED},
    PipelineStep.EXTRACT_ENTITIES: {
        PipelineCheckpoint.PENDING_ENTITY_EXTRACTIONS_MATERIALIZED,
        PipelineCheckpoint.ENTITIES_EXTRACTED,
    },
    PipelineStep.EXTRACT_RELATIONSHIPS: {
        PipelineCheckpoint.PENDING_RELATIONSHIP_EXTRACTIONS_MATERIALIZED,
        PipelineCheckpoint.RELATIONSHIPS_EXTRACTED,
    },
    PipelineStep.EXPORT_KNOWLEDGE: {PipelineCheckpoint.KNOWLEDGE_EXPORTED},
}
