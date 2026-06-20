from typing import Protocol

from wukong_engine.core.pipeline.model.values import PipelineCheckpoint, PipelineCheckpointStatus, PipelineStep


class PipelineStore(Protocol):
    """Store for managing the state of the pipeline."""

    def initialize_all_steps(self) -> None:
        """Initialize all steps and their associated checkpoints."""
        ...

    def set_checkpoint_status(self, checkpoint: PipelineCheckpoint, status: PipelineCheckpointStatus) -> None:
        """Set the status of a specific checkpoint."""
        ...

    def get_checkpoint_status(self, checkpoint: PipelineCheckpoint) -> PipelineCheckpointStatus:
        """Get the status of a specific checkpoint."""
        ...

    def is_checkpoint_completed(self, checkpoint: PipelineCheckpoint) -> bool:
        """Whether a specific checkpoint has been completed."""
        ...

    def reset_step_checkpoints(self, step: PipelineStep) -> None:
        """Reset all checkpoints associated with a specific pipeline step."""
        ...

    def reset_dependent_checkpoints(self, step: PipelineStep) -> None:
        """Reset all checkpoints dependent on a specific pipeline step."""
        ...

    def is_step_completed(self, step: PipelineStep) -> bool:
        """Whether all checkpoints for a specific pipeline step are completed."""
        ...

    def are_dependencies_completed(self, step: PipelineStep) -> bool:
        """Whether all step dependencies for a specific pipeline step are completed."""
        ...

    def clear(self) -> None:
        """Reset the pipeline store."""
        ...
