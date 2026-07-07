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
from wukong_engine.core.graph.model import RelationshipType
from wukong_engine.core.graph.model.values import EntityTypeName

from .batch import ExtractionBatch
from .job import ExtractionJob


@dataclass(frozen=True)
class ExtractionSpec:
    """Structured specification for an extraction job."""

    document_context: str
    task: str
    definitions: str
    source_text: str
    response_schema: dict[str, Any] | None = None


@dataclass(frozen=True)
class ExtractionRequest:
    """Request to process an extraction job, containing the job and its specification."""

    job: ExtractionJob
    spec: ExtractionSpec
    reasoning_effort: ReasoningEffort | None = None
    temperature: float | None = None


@dataclass(frozen=True)
class ExtractionResult:
    """Extraction result for a single extraction job.

    Contains the final job status, the extracted data (if successful), and any errors encountered during processing.
    """

    status: JobStatus
    data: dict[str, Any] = field(default_factory=dict)
    metrics: TokenUsageMetrics | None = None
    error: str | None = None
    error_severity: ErrorSeverity | None = None
    retry_policy: JobRetryPolicy | None = None


@dataclass(frozen=True)
class BatchSubmissionRequest:
    """Request to submit a batch of extraction requests.

    Each request contains the extraction job and its associated specification.
    """

    batch: Iterable[ExtractionRequest]


@dataclass(frozen=True)
class BatchSubmissionResult:
    """Submission result for a batch of extraction requests.

    Contains the submitted batch.
    If the submission failed, the batch will be None and the error details will be provided.
    """

    batch: ExtractionBatch | None
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


@dataclass(frozen=True)
class RelationshipExtractionRequestContext:
    """Required information to build a relationship extraction request for a given chunk."""

    relationship_types: tuple[RelationshipType, ...]
    chunk_entity_type_names: tuple[EntityTypeName, ...]
    parent_document_entity_type_names: tuple[EntityTypeName, ...]
