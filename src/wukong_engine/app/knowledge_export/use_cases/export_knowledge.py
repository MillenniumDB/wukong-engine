from wukong_engine.app.knowledge_export.ports import KnowledgeExporter
from wukong_engine.app.staging.ports import UnitOfWork
from wukong_engine.core.pipeline.model.values import PipelineCheckpoint, PipelineCheckpointStatus


# TODO: Test exporter
# TODO: Reset method resets export dir by calling exporter.reset() and resets checkpoint status
# TODO: Error handling and logging inside execute method
class ExportKnowledge:
    """Use case for exporting extracted knowledge to a specified output format."""

    def __init__(self, uow: UnitOfWork, exporter: KnowledgeExporter) -> None:
        """Initialize the use case with its dependencies."""
        self._uow = uow
        self._exporter = exporter

    def execute(self, exports_uri: str) -> None:
        """Export the extracted knowledge to output files using a specified format."""
        self._exporter.export(exports_uri)
        with self._uow as tx:
            tx.pipeline.set_checkpoint_status(PipelineCheckpoint.KNOWLEDGE_EXPORTED, PipelineCheckpointStatus.COMPLETED)

    def reset(self) -> None:
        """Reset the knowledge export state."""
