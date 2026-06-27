"""State objects for data extraction."""

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from wukong_engine.app.data_extraction.elements.values import (
    JobErrorLevel,
    JobRetryPolicy,
    JobStatus,
    TokenUsageMetrics,
)
from wukong_engine.app.llm.elements.values import ReasoningEffort
from wukong_engine.app.llm.model import LLM

from .batch import ExtractionBatch
from .job import ExtractionJob


@dataclass(frozen=True)
class ExtractionContext:
    """Generic structured context for an extraction job."""

    document_context: str
    task: str
    definitions: str
    source_text: str
    response_schema: dict[str, Any] | None = None


@dataclass(frozen=True)
class ExtractionRequest:
    """Request containing an extraction job and its derived context and override parameters."""

    job: ExtractionJob
    context: ExtractionContext
    model: LLM | None = None
    reasoning_effort: ReasoningEffort | None = None
    temperature: float | None = None


@dataclass(frozen=True)
class ExtractionResult:
    """Extraction result containing the job and the extracted data."""

    job: ExtractionJob
    status: JobStatus
    data: dict[str, Any] = field(default_factory=dict)
    metrics: TokenUsageMetrics | None = None
    error: str | None = None
    error_level: JobErrorLevel | None = None
    retry_policy: JobRetryPolicy | None = None


@dataclass(frozen=True)
class BatchSubmissionRequest:
    """Request to submit a batch of extraction requests."""

    batch: Iterable[ExtractionRequest]


@dataclass(frozen=True)
class BatchSubmissionResult:
    """Submission result for a batch of extraction requests."""

    batch: ExtractionBatch
    jobs: tuple[ExtractionJob, ...]
