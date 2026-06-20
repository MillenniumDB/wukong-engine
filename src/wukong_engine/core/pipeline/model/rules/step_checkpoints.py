from wukong_engine.core.pipeline.model.values import PipelineCheckpoint, PipelineStep

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
}
