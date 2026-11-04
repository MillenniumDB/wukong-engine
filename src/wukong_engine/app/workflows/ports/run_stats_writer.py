"""Port for recording the statistics of a run next to its export."""

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from wukong_engine.app.workflows.run_stats import RunStats


class RunStatsWriter(Protocol):
    """Records the statistics of a run alongside the files it exported."""

    def write(self, stats: RunStats, directory: str) -> None:
        """Record the statistics of a run in an export directory.

        Args:
            stats: Statistics of the run.
            directory: Directory holding the files the run exported.
        """
        ...
