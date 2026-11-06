"""Tests for the progress lines the extraction metrics tracker shows."""

import logging
from types import SimpleNamespace

import pytest

from wukong_engine.app.data_extraction.model.values import ExecutionMode
from wukong_engine.app.data_extraction.services import ExtractionMetricsTracker
from wukong_engine.app.shared.progress import PROGRESS_LOGGER_NAME
from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.pipeline.model.values import PipelineStep


class PendingSourcesRepository:
    """Extraction repository reporting a fixed number of sources pending extraction."""

    def __init__(self, pending: int) -> None:
        """Initialize the repository with the number of pending sources."""
        self.pending = pending

    def get_extraction_metrics(self, _: ContextLevel, __: object) -> SimpleNamespace:
        """Report the pending sources."""
        return SimpleNamespace(source_counts={'pending': self.pending})


def test_batch_uploads_show_their_progress_after_each_batch(caplog: pytest.LogCaptureFixture) -> None:
    """Show the requests to upload, then the requests uploaded so far after each batch, failed uploads included."""
    tracker = ExtractionMetricsTracker(
        PendingSourcesRepository(pending=2500),  # type: ignore[arg-type]
        ExecutionMode.BATCH,
        PipelineStep.EXTRACT_ENTITIES,
    )
    tracker._context_level = ContextLevel.CHUNK  # Without collecting the full metrics, which the test omits
    prefix = f'  {PipelineStep.EXTRACT_ENTITIES.value} (CHUNKS): '

    with caplog.at_level(logging.INFO, logger=PROGRESS_LOGGER_NAME):
        tracker.start_uploads(batch_size=1000)
        tracker.record_upload(1000, uploaded=True)
        tracker.record_upload(1000, uploaded=False)
        tracker.record_upload(500, uploaded=True)

    lines = [record.getMessage() for record in caplog.records]
    assert lines[0] == f'{prefix}uploading 2,500 requests in batches of up to 1,000...'
    assert lines[1].startswith(f'{prefix}uploaded 1,000/2,500 requests (40.0%) in 1 batch, ETA ')
    assert lines[2].startswith(
        f'{prefix}uploaded 1,000/2,500 requests (40.0%) in 1 batch, 1 failed to upload (retried next run), ETA '
    )
    assert (
        lines[3] == f'{prefix}uploaded 1,500/2,500 requests (60.0%) in 2 batches, 1 failed to upload (retried next run)'
    )


def test_batch_uploads_show_nothing_without_pending_requests(caplog: pytest.LogCaptureFixture) -> None:
    """Stay silent in the runs that only wait for submitted batches, with nothing left to upload."""
    tracker = ExtractionMetricsTracker(
        PendingSourcesRepository(pending=0),  # type: ignore[arg-type]
        ExecutionMode.BATCH,
        PipelineStep.EXTRACT_ENTITIES,
    )
    tracker._context_level = ContextLevel.CHUNK  # Without collecting the full metrics, which the test omits

    with caplog.at_level(logging.INFO, logger=PROGRESS_LOGGER_NAME):
        tracker.start_uploads(batch_size=1000)
        tracker.record_upload(1000, uploaded=True)

    assert caplog.records == []
