"""SQLite-backed pipeline checkpoint store."""

import sqlite3
import time

from wukong_engine.app.staging.ports import PipelineStore
from wukong_engine.core.pipeline.model.values import PipelineCheckpoint, PipelineCheckpointStatus, PipelineStep


class SQLitePipelineStore(PipelineStore):
    """SQLite implementation of the PipelineStore."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialize the staging store with a SQLite connection."""
        self._conn = conn

    def initialize_all_steps(self) -> None:
        """Initialize all steps and their associated checkpoints."""
        checkpoints: set[PipelineCheckpoint] = set()
        for step in PipelineStep:
            checkpoints |= step.checkpoints
        self._conn.executemany(
            """
            INSERT OR IGNORE INTO pipeline_checkpoints (
                checkpoint_name,
                checkpoint_status,
                updated_at
            ) VALUES (?, ?, ?)
            """,
            [
                (checkpoint.value, PipelineCheckpointStatus.PENDING.value, int(time.time() * 1000))
                for checkpoint in checkpoints
            ],
        )

    def set_checkpoint_status(self, checkpoint: PipelineCheckpoint, status: PipelineCheckpointStatus) -> None:
        """Set the status of a specific checkpoint."""
        self._conn.execute(
            """
            INSERT INTO pipeline_checkpoints (
                checkpoint_name,
                checkpoint_status,
                updated_at
            ) VALUES (?, ?, ?)
            ON CONFLICT(checkpoint_name) DO UPDATE SET
                checkpoint_status = excluded.checkpoint_status,
                updated_at = excluded.updated_at
            """,
            (checkpoint.value, status.value, int(time.time() * 1000)),
        )

    def get_checkpoint_status(self, checkpoint: PipelineCheckpoint) -> PipelineCheckpointStatus:
        """Get the status of a specific checkpoint."""
        row = self._conn.execute(
            """
            SELECT checkpoint_status
            FROM pipeline_checkpoints
            WHERE checkpoint_name = ?
            """,
            (checkpoint.value,),
        ).fetchone()

        # If no row is found, treat it as PENDING
        if row is None:
            return PipelineCheckpointStatus.PENDING

        return PipelineCheckpointStatus(row['checkpoint_status'])

    def is_checkpoint_completed(self, checkpoint: PipelineCheckpoint) -> bool:
        """Whether a specific checkpoint has been completed."""
        return self.get_checkpoint_status(checkpoint) == PipelineCheckpointStatus.COMPLETED

    def reset_step_checkpoints(self, step: PipelineStep) -> None:
        """Reset all checkpoints associated with a specific pipeline step."""
        for checkpoint in step.checkpoints:
            self.set_checkpoint_status(checkpoint, PipelineCheckpointStatus.PENDING)

    def reset_dependent_checkpoints(self, step: PipelineStep) -> None:
        """Reset all checkpoints dependent on a specific pipeline step."""
        self.reset_step_checkpoints(step)
        for dependent_step in step.is_required_by:
            self.reset_step_checkpoints(dependent_step)

    def is_step_completed(self, step: PipelineStep) -> bool:
        """Whether all checkpoints for a specific pipeline step are completed."""
        return all(self.is_checkpoint_completed(checkpoint) for checkpoint in step.checkpoints)

    def are_dependencies_completed(self, step: PipelineStep) -> bool:
        """Whether all step dependencies for a specific pipeline step are completed."""
        return all(self.is_step_completed(dependency) for dependency in step.depends_on)

    def clear(self) -> None:
        """Reset the pipeline store."""
        self._conn.execute(
            """
            UPDATE pipeline_checkpoints
            SET checkpoint_status = ?, updated_at = ?
            """,
            (PipelineCheckpointStatus.PENDING.value, int(time.time() * 1000)),
        )
