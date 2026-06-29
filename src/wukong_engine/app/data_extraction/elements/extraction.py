"""State objects for data extraction."""

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from wukong_engine.app.data_extraction.elements.values import (
    BatchStatus,
    ErrorSeverity,
    JobRetryPolicy,
    JobStatus,
    TokenUsageMetrics,
)
from wukong_engine.app.llm.elements import LLMBatchResult
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
    """Request to process an extraction job, containing the job and its context."""

    job: ExtractionJob
    context: ExtractionContext
    model: LLM | None = None
    reasoning_effort: ReasoningEffort | None = None
    temperature: float | None = None


@dataclass(frozen=True)
class ExtractionResult:
    """Extraction result for a single extraction job.

    Contains the job, its status, the extracted data (if successful), and any errors encountered during processing.
    """

    status: JobStatus
    data: dict[str, Any] = field(default_factory=dict)
    metrics: TokenUsageMetrics | None = None
    error: str | None = None
    error_severity: ErrorSeverity | None = None
    retry_policy: JobRetryPolicy | None = None


@dataclass(frozen=True)
class BatchSubmissionRequest:
    """Request to submit a batch of extraction requests."""

    batch: Iterable[ExtractionRequest]


@dataclass(frozen=True)
class BatchSubmissionResult:
    """Submission result for a batch of extraction requests.

    Contains the batch and its associated jobs.
    If the submission failed, the batch will be None and the error details will be provided.
    """

    batch: ExtractionBatch | None
    jobs: tuple[ExtractionJob, ...]
    error: str | None = None
    error_severity: ErrorSeverity | None = None


@dataclass(frozen=True)
class BatchStatusResult:
    """Result of checking the status of a batch with the external provider."""

    status: BatchStatus
    error: str | None = None


@dataclass(frozen=True)
class CompletedBatchResult:
    """Results for a completed batch retrieved from the external provider."""

    results: tuple[LLMBatchResult, ...] | None
    error: str | None = None
