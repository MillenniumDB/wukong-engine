from wukong_engine.core.pipeline.model.values import PipelineStep

# Mapping of pipeline steps to the steps that must be completed before they can be executed
STEP_DEPENDENCIES: dict[PipelineStep, set[PipelineStep]] = {
    PipelineStep.INGEST_DOCUMENTS: set(),
    PipelineStep.EXTRACT_ENTITIES: {PipelineStep.INGEST_DOCUMENTS},
    PipelineStep.EXTRACT_RELATIONSHIPS: {PipelineStep.INGEST_DOCUMENTS, PipelineStep.EXTRACT_ENTITIES},
}
