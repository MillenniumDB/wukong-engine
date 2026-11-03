"""Provides the LocalRunStatsWriter class."""

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from wukong_engine.app.workflows import RunStats
from wukong_engine.app.workflows.ports import RunStatsWriter

RUN_STATS_FILENAME = 'stats.json'


class LocalRunStatsWriter(RunStatsWriter):
    """Writes the statistics of a run as a JSON file in its export directory on the local filesystem."""

    def write(self, stats: RunStats, directory: str) -> None:
        """Write the statistics of a run to ``stats.json`` in an export directory.

        Totals the report derives (durations, tokens, the overall estimated cost, and exported nodes, edges and bytes)
        are written along
        with the stats they are derived from, so the file can be read without recomputing them.

        Args:
            stats: Statistics of the run.
            directory: Directory holding the files the run exported.
        """
        content: dict[str, Any] = asdict(stats)
        for step in ('entities', 'relationships'):
            content[step]['tokens']['total'] = getattr(stats, step).tokens.total
            for level, level_stats in zip(content[step]['levels'], getattr(stats, step).levels, strict=True):
                level['tokens']['total'] = level_stats.tokens.total
        content['totals'] = {
            'this_run_seconds': sum(stats.this_run_seconds.values()),
            'all_runs_seconds': sum(stats.all_runs_seconds.values()),
            'tokens': asdict(stats.tokens) | {'total': stats.tokens.total},
            'estimated_cost_usd': stats.estimated_cost_usd,
        }
        if stats.export is not None:
            content['export']['total_nodes'] = sum(stats.export.nodes.values())
            content['export']['total_edges'] = sum(stats.export.edges.values())
            content['export']['total_bytes'] = stats.export.total_bytes
        path = Path(directory) / RUN_STATS_FILENAME
        path.write_text(json.dumps(content, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
