"""Tests for the reset of the extraction use cases, which must not leave batches billing at the provider."""

import asyncio
from pathlib import Path

import pytest

from wukong_engine.app.data_extraction.services import (
    EntityExtractionRepository,
    ExtractionMetricsTracker,
    RelationshipExtractionRepository,
)
from wukong_engine.app.data_extraction.use_cases import ExtractEntities, ExtractRelationships
from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.knowledge.model import KnowledgeModel
from wukong_engine.infrastructure.persistence.sqlite import (
    SQLiteSessionFactory,
    SQLiteUnitOfWork,
    initialize_sqlite_database,
)


class RecordingEntityRepository(EntityExtractionRepository):
    """Entity extraction repository recording its reset in a shared call log."""

    def __init__(self, calls: list[str]) -> None:
        """Initialize the repository without a unit of work, since its reset doesn't reach the database."""
        self.calls = calls

    def reset(self) -> None:
        """Record the reset."""
        self.calls.append('reset repository')


class RecordingRelationshipRepository(RelationshipExtractionRepository):
    """Relationship extraction repository recording its reset in a shared call log."""

    def __init__(self, calls: list[str]) -> None:
        """Initialize the repository without a unit of work, since its reset doesn't reach the database."""
        self.calls = calls

    def reset(self) -> None:
        """Record the reset."""
        self.calls.append('reset repository')


class RecordingMetricsTracker(ExtractionMetricsTracker):
    """Metrics tracker recording its reset in a shared call log."""

    def __init__(self, calls: list[str]) -> None:
        """Initialize the tracker without a repository, since its reset doesn't use one."""
        self.calls = calls

    def reset(self) -> None:
        """Record the reset."""
        self.calls.append('reset metrics')


class RecordingSynchronizer:
    """Batch synchronizer recording the cancellation requests in a shared call log."""

    def __init__(self, calls: list[str]) -> None:
        """Initialize the synchronizer with the shared call log."""
        self.calls = calls

    async def synchronize(self, knowledge_model: KnowledgeModel) -> None:
        """Not used by these tests."""
        raise NotImplementedError

    async def request_active_batch_cancellations(self) -> None:
        """Record the cancellation requests."""
        self.calls.append('request batch cancellations')


class UnusedEngine:
    """Extraction engine for tests in which no extraction runs."""

    async def run(self, context_level: ContextLevel, knowledge_model: KnowledgeModel) -> None:
        """Not used by these tests."""
        raise NotImplementedError


@pytest.mark.parametrize('use_case_type', [ExtractEntities, ExtractRelationships])
def test_reset_requests_the_cancellation_of_active_batches_before_discarding_them(
    tmp_path: Path,
    use_case_type: type[ExtractEntities | ExtractRelationships],
) -> None:
    """Request the cancellation of the active batches before resetting the extraction state that tracks them."""
    factory = SQLiteSessionFactory(db_path=tmp_path / 'staging.db')
    initialize_sqlite_database(db_path=factory.db_path, connection_factory=factory)
    calls: list[str] = []
    synchronizer = RecordingSynchronizer(calls)
    tracker = RecordingMetricsTracker(calls)
    uow = SQLiteUnitOfWork(connection_factory=factory)
    if use_case_type is ExtractEntities:
        use_case = ExtractEntities(uow, RecordingEntityRepository(calls), UnusedEngine(), synchronizer, tracker)
    else:
        use_case = ExtractRelationships(
            uow, RecordingRelationshipRepository(calls), UnusedEngine(), synchronizer, tracker
        )

    asyncio.run(use_case.reset())

    assert calls == ['request batch cancellations', 'reset repository', 'reset metrics']
