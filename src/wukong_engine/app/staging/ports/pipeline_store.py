"""Port for the pipeline checkpoint store."""

from typing import Protocol

from wukong_engine.core.pipeline.model.values import PipelineCheckpoint, PipelineCheckpointStatus, PipelineStep


class PipelineStore(Protocol):
    """Store for managing the state of the pipeline."""

    def initialize_all_steps(self) -> None:
        """Initialize all steps and their associated checkpoints."""
        ...

    def set_checkpoint_status(self, checkpoint: PipelineCheckpoint, status: PipelineCheckpointStatus) -> None:
        """Set the status of a specific checkpoint.

        Args:
            checkpoint: Checkpoint to update.
            status: New status of the checkpoint.
        """
        ...

    def get_checkpoint_status(self, checkpoint: PipelineCheckpoint) -> PipelineCheckpointStatus:
        """Get the status of a specific checkpoint.

        Args:
            checkpoint: Checkpoint to look up.

        Returns:
            The stored status of the checkpoint, or PENDING if it has never been recorded.
        """
        ...

    def is_checkpoint_completed(self, checkpoint: PipelineCheckpoint) -> bool:
        """Whether a specific checkpoint has been completed.

        Args:
            checkpoint: Checkpoint to check.

        Returns:
            True if the checkpoint's status is COMPLETED, False otherwise.
        """
        ...

    def reset_step_checkpoints(self, step: PipelineStep) -> None:
        """Reset all checkpoints associated with a specific pipeline step, along with its recorded run durations.

        Args:
            step: Step whose checkpoints are set back to PENDING and whose run durations are cleared.
        """
        ...

    def record_step_run(self, step: PipelineStep, duration: float) -> None:
        """Record how long a run of a pipeline step took, whether or not it completed the step.

        Args:
            step: Step that ran.
            duration: Time the step ran for, in seconds.
        """
        ...

    def get_step_durations(self) -> dict[PipelineStep, float]:
        """Get the time spent running each pipeline step since its checkpoints were last reset.

        Returns:
            The summed duration of the recorded runs of each step that has any, in seconds.
        """
        ...

    def reset_dependent_checkpoints(self, step: PipelineStep) -> None:
        """Reset all checkpoints dependent on a specific pipeline step.

        Resets the step's own checkpoints and those of the steps that directly depend on it.

        Args:
            step: Step whose checkpoints, and those of its direct dependents, are set back to PENDING.
        """
        ...

    def is_step_completed(self, step: PipelineStep) -> bool:
        """Whether all checkpoints for a specific pipeline step are completed.

        Args:
            step: Step to check.

        Returns:
            True if every checkpoint of the step is COMPLETED, False otherwise.
        """
        ...

    def are_dependencies_completed(self, step: PipelineStep) -> bool:
        """Whether all step dependencies for a specific pipeline step are completed.

        Args:
            step: Step whose direct dependencies are checked.

        Returns:
            True if every step it depends on is completed, False otherwise.
        """
        ...

    def clear(self) -> None:
        """Reset the pipeline store, setting every checkpoint back to PENDING and clearing every run duration."""
        ...
