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
from wukong_engine.core.knowledge.elements import Entity
from wukong_engine.core.knowledge.model import RelationshipType
from wukong_engine.core.knowledge.model.values import EntityTypeName

from .batch import ExtractionBatch
from .job import ExtractionJob


@dataclass(frozen=True, slots=True)
class ExtractionSpec:
    """Structured specification for an extraction job.

    `definitions` are shared by every job extracting the same types, while `source_definitions` are specific to
    the job's source (e.g. the entities available in it).

    Attributes:
        document_context: Rendered domain/language context of the documents being processed.
        task: Rendered description of the extraction task.
        definitions: Rendered definitions of the types to extract, shared across jobs extracting the same types.
        source_text: Text of the source to extract from.
        response_schema: JSON schema the LLM response must follow. If None, no structured output is enforced.
        source_definitions: Rendered definitions specific to the job's source. If None, none are included.
    """

    document_context: str
    task: str
    definitions: str
    source_text: str
    response_schema: dict[str, Any] | None = None
    source_definitions: str | None = None


@dataclass(frozen=True, slots=True)
class ExtractionRequest:
    """Request to process an extraction job, containing the job and its specification.

    Attributes:
        job: Extraction job to process.
        spec: Specification used to render the job's prompt.
        reasoning_effort: Reasoning effort to request from the LLM. If None, the LLM client picks its default.
        temperature: Sampling temperature to request from the LLM. If None, the LLM client picks its default.
    """

    job: ExtractionJob
    spec: ExtractionSpec
    reasoning_effort: ReasoningEffort | None = None
    temperature: float | None = None


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    """Extraction result for a single extraction job.

    Contains the final job status, the extracted data (if successful), and any errors encountered during processing.

    Attributes:
        status: Final status of the job.
        data: Extracted data parsed from the LLM response. Empty if the extraction failed.
        metrics: Token usage of the LLM call, if available.
        error: Error message, if the extraction failed.
        error_severity: Severity of the error, if the extraction failed.
        retry_policy: How the failed job may be retried, if the extraction failed.
    """

    status: JobStatus
    data: dict[str, Any] = field(default_factory=dict)
    metrics: TokenUsageMetrics | None = None
    error: str | None = None
    error_severity: ErrorSeverity | None = None
    retry_policy: JobRetryPolicy | None = None


@dataclass(frozen=True, slots=True)
class BatchSubmissionRequest:
    """Request to submit a batch of extraction requests.

    Each request contains the extraction job and its associated specification.

    Attributes:
        batch: Extraction requests to submit together as one provider batch.
    """

    batch: Iterable[ExtractionRequest]


@dataclass(frozen=True, slots=True)
class BatchSubmissionResult:
    """Submission result for a batch of extraction requests.

    Contains the submitted batch.
    If the submission failed, the batch will be None and the error details will be provided.

    Attributes:
        batch: Submitted batch, or None if the submission failed.
        error: Error message, if the submission failed.
        error_severity: Severity of the error, if the submission failed.
    """

    batch: ExtractionBatch | None
    error: str | None = None
    error_severity: ErrorSeverity | None = None


@dataclass(frozen=True, slots=True)
class BatchStatusResult:
    """Result of checking the status of a batch with the external provider.

    Attributes:
        status: Status of the batch reported by the provider, or its last known status if the check failed.
        error: Error message, if the status could not be retrieved or mapped.
    """

    status: BatchStatus
    error: str | None = None


@dataclass(frozen=True, slots=True)
class CompletedBatchResult:
    """Results for a completed batch retrieved from the external provider.

    Attributes:
        results: Per-request results of the batch, or None if they could not be retrieved.
        error: Error message, if the results could not be retrieved.
    """

    results: tuple[LLMBatchResult, ...] | None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class RelationshipExtractionRequestContext:
    """Required information to build a relationship extraction request for a given chunk.

    Attributes:
        relationship_types: Relationship types that can be extracted from the chunk.
        chunk_entity_type_names: Names of the compatible entity types available in the chunk itself.
        parent_document_entity_type_names: Names of the compatible entity types available in the chunk's parent
            document.
    """

    relationship_types: tuple[RelationshipType, ...]
    chunk_entity_type_names: tuple[EntityTypeName, ...]
    parent_document_entity_type_names: tuple[EntityTypeName, ...]


@dataclass(frozen=True, slots=True)
class RelationshipExtractionRequestObjects:
    """Required objects to build a relationship extraction request for a given chunk.

    Attributes:
        relationship_types: Relationship types that can be extracted from the chunk.
        chunk_entities: Compatible entities linked to the chunk itself.
        parent_document_entities: Compatible entities linked to the chunk's parent document.
    """

    relationship_types: tuple[RelationshipType, ...]
    chunk_entities: tuple[Entity, ...]
    parent_document_entities: tuple[Entity, ...]
