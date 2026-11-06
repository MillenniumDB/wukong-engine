"""Tests for the statistics of a run: their formatting, the cost estimate and the stats file written with an export."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from wukong_engine.app.data_extraction.elements.values import ExtractionStatus, TokenUsageMetrics
from wukong_engine.app.data_extraction.model.values import ExecutionMode
from wukong_engine.app.knowledge_export.elements import ExportReport
from wukong_engine.app.llm.model import LLMRegistry
from wukong_engine.app.llm.model.values import TokenRates
from wukong_engine.app.workflows import RunStatsService
from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.pipeline.model.values import PipelineStep
from wukong_engine.infrastructure.persistence.sqlite import (
    SQLiteSessionFactory,
    SQLiteUnitOfWork,
    initialize_sqlite_database,
)
from wukong_engine.infrastructure.storage.filesystem import LocalRunStatsWriter

RATES = TokenRates(input=1.0, cached_input=0.1, cache_write=1.25, output=4.0, as_of='2026-01-01', batch_discount=0.5)


class ChunkExtractionRepository:
    """Extraction repository holding 10 chunk sources, 9 extracted and 1 failed, with the given token usage."""

    def __init__(self, usage: dict[ExecutionMode, TokenUsageMetrics]) -> None:
        """Initialize the repository with the token usage of each execution mode."""
        self.usage = usage

    def get_extraction_metrics(self, context_level: ContextLevel, _: object) -> SimpleNamespace:
        """Report the chunk sources and their objects, and no document sources."""
        if context_level is not ContextLevel.CHUNK:
            return SimpleNamespace(total_sources=0)
        return SimpleNamespace(
            total_sources=10,
            source_counts={'completed': 9, 'failed': 1},
            object_count=40,
            object_mentions=55,
            source_status_counts={ExtractionStatus.COMPLETED: 9, ExtractionStatus.FAILED: 1},
        )

    def get_token_usage_by_execution_mode(self, _: ContextLevel) -> dict[ExecutionMode, TokenUsageMetrics]:
        """Report the token usage of each execution mode."""
        return self.usage


def _service(tmp_path: Path, usage: dict[ExecutionMode, TokenUsageMetrics]) -> RunStatsService:
    """Build the stats service over an empty workspace whose two extraction steps both used the given tokens."""
    factory = SQLiteSessionFactory(db_path=tmp_path / 'staging.db')
    initialize_sqlite_database(db_path=factory.db_path, connection_factory=factory)
    repository = ChunkExtractionRepository(usage)
    return RunStatsService(
        uow=SQLiteUnitOfWork(connection_factory=factory),
        entity_repository=repository,
        relationship_repository=repository,
        model=LLMRegistry.default_model(),
        execution_mode=ExecutionMode.BATCH,
        export_format='MillenniumDB',
        writer=LocalRunStatsWriter(),
    )


def test_batch_tokens_are_priced_at_the_discount_and_reasoning_as_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Price each category at its rate, reasoning tokens at the output rate and batch tokens at half the price."""
    monkeypatch.setattr(LLMRegistry, 'token_rates', classmethod(lambda _, __: RATES))
    usage = {
        # 1M input ($1) + 1M cached ($0.10) + 0.4M cache writes ($0.50) + 0.5M output and 0.5M reasoning ($4)
        ExecutionMode.REALTIME: TokenUsageMetrics(1_000_000, 1_000_000, 400_000, 500_000, 500_000),
        # 2M input ($2), at half price
        ExecutionMode.BATCH: TokenUsageMetrics(2_000_000, 0, 0, 0, 0),
    }

    stats = _service(tmp_path, usage).collect({})

    assert stats.entities.estimated_cost_usd == pytest.approx(5.6 + 1.0)
    assert stats.estimated_cost_usd == pytest.approx(2 * 6.6)
    assert stats.entities.tokens.total == 5_400_000
    assert stats.token_rates_as_of == RATES.as_of
    assert 'had on 2026-01-01' in str(stats)
    assert stats.step_summary(PipelineStep.EXTRACT_ENTITIES) == (
        'CHUNKS 9/10 (1 failed) sources, 40 entities, 5.40 M tokens (~$6.60)'
    )


def test_no_cost_is_estimated_for_a_model_without_rates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Leave the cost unknown, rather than zero, when the model's rates aren't known."""
    monkeypatch.setattr(LLMRegistry, 'token_rates', classmethod(lambda _, __: None))

    stats = _service(tmp_path, dict.fromkeys(ExecutionMode, TokenUsageMetrics(5, 0, 0, 5, 0))).collect({})

    assert stats.estimated_cost_usd is None
    assert 'no cost is estimated' in str(stats)


def test_the_stats_file_records_the_derived_totals_and_export_size(tmp_path: Path) -> None:
    """Write the totals the report shows next to the stats, so the file can be read without recomputing them."""
    export_dir = tmp_path / 'exports'
    export_dir.mkdir()
    export = ExportReport(
        directory=str(export_dir),
        nodes={'Document': 2, 'Chunk': 3},
        edges={'ChunkOf': 3, 'ExtractedFrom': 0},
        relationship_provenance=0,
        files={'knowledge_graph.qm': 1000},
    )
    service = _service(tmp_path, dict.fromkeys(ExecutionMode, TokenUsageMetrics(5, 0, 0, 5, 0)))
    stats = service.collect({PipelineStep.EXPORT_KNOWLEDGE: 0.5}, export)

    service.save(stats, str(export_dir))

    content = json.loads((export_dir / 'stats.json').read_text(encoding='utf-8'))
    assert content['totals']['tokens']['total'] == 40
    assert content['totals']['this_run_seconds'] == 0.5
    assert content['entities']['levels'][0]['tokens']['total'] == 20
    assert content['export']['total_bytes'] == 1000
    assert (content['export']['total_nodes'], content['export']['total_edges']) == (5, 3)
    assert content['export']['nodes'] == {'Document': 2, 'Chunk': 3}
