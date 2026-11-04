"""SQLite-backed pipeline checkpoint store."""

import sqlite3
import time

from wukong_engine.app.staging.ports import PipelineStore
from wukong_engine.core.pipeline.model.values import PipelineCheckpoint, PipelineCheckpointStatus, PipelineStep


class SQLitePipelineStore(PipelineStore):
    """SQLite implementation of the PipelineStore."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialize the staging store with a SQLite connection.

        Args:
            conn: Open SQLite connection used for all queries.
        """
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
        """Set the status of a specific checkpoint.

        Inserts the checkpoint if it doesn't exist yet and refreshes its update timestamp.

        Args:
            checkpoint: Checkpoint to update.
            status: New status of the checkpoint.
        """
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
        """Get the status of a specific checkpoint.

        Args:
            checkpoint: Checkpoint to look up.

        Returns:
            The stored status, or PENDING if the checkpoint has no row.
        """
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
        """Check whether a specific checkpoint has been completed.

        Args:
            checkpoint: Checkpoint to check.

        Returns:
            True if the checkpoint's status is COMPLETED, False otherwise.
        """
        return self.get_checkpoint_status(checkpoint) == PipelineCheckpointStatus.COMPLETED

    def reset_step_checkpoints(self, step: PipelineStep) -> None:
        """Reset all checkpoints associated with a specific pipeline step, along with its recorded run durations.

        Args:
            step: Step whose checkpoints are set back to PENDING and whose run durations are cleared.
        """
        for checkpoint in step.checkpoints:
            self.set_checkpoint_status(checkpoint, PipelineCheckpointStatus.PENDING)
        self._conn.execute('DELETE FROM pipeline_step_runs WHERE step_name = ?', (step.value,))

    def record_step_run(self, step: PipelineStep, duration: float) -> None:
        """Record how long a run of a pipeline step took, whether or not it completed the step.

        Args:
            step: Step that ran.
            duration: Time the step ran for, in seconds.
        """
        self._conn.execute(
            'INSERT INTO pipeline_step_runs (step_name, finished_at, duration_ms) VALUES (?, ?, ?)',
            (step.value, int(time.time() * 1000), round(duration * 1000)),
        )

    def get_step_durations(self) -> dict[PipelineStep, float]:
        """Get the time spent running each pipeline step since its checkpoints were last reset.

        Returns:
            The summed duration of the recorded runs of each step that has any, in seconds.
        """
        rows = self._conn.execute(
            'SELECT step_name, SUM(duration_ms) AS total_ms FROM pipeline_step_runs GROUP BY step_name',
        )
        return {PipelineStep(row['step_name']): row['total_ms'] / 1000 for row in rows}

    def reset_dependent_checkpoints(self, step: PipelineStep) -> None:
        """Reset all checkpoints dependent on a specific pipeline step.

        Resets the step's own checkpoints and those of the steps that directly depend on it.

        Args:
            step: Step whose checkpoints, and those of its direct dependents, are set back to PENDING.
        """
        self.reset_step_checkpoints(step)
        for dependent_step in step.is_required_by:
            self.reset_step_checkpoints(dependent_step)

    def is_step_completed(self, step: PipelineStep) -> bool:
        """Check whether all checkpoints for a specific pipeline step are completed.

        Args:
            step: Step to check.

        Returns:
            True if every checkpoint of the step is COMPLETED, False otherwise.
        """
        return all(self.is_checkpoint_completed(checkpoint) for checkpoint in step.checkpoints)

    def are_dependencies_completed(self, step: PipelineStep) -> bool:
        """Check whether all step dependencies for a specific pipeline step are completed.

        Args:
            step: Step whose direct dependencies are checked.

        Returns:
            True if every step it depends on is completed, False otherwise.
        """
        return all(self.is_step_completed(dependency) for dependency in step.depends_on)

    def clear(self) -> None:
        """Reset the pipeline store, setting every checkpoint back to PENDING and clearing every run duration."""
        self._conn.execute(
            """
            UPDATE pipeline_checkpoints
            SET checkpoint_status = ?, updated_at = ?
            """,
            (PipelineCheckpointStatus.PENDING.value, int(time.time() * 1000)),
        )
        self._conn.execute('DELETE FROM pipeline_step_runs')
