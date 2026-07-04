"""Batches for data extraction."""

from dataclasses import dataclass
from typing import Self

from wukong_engine.app.llm.model.values import LLMProvider

from .values import BatchStatus, ExtractionBatchId


@dataclass(frozen=True)
class ExtractionBatch:
    """Batch of extraction jobs for processing."""

    id: ExtractionBatchId
    provider: LLMProvider
    provider_id: str
    status: BatchStatus
    created_at: int | None = None

    def __str__(self) -> str:
        """User-friendly string representation of the extraction batch."""
        batch = f'Batch ID: {self.id}\n'
        batch += f'Provider Batch ID: {self.provider_id}\n'
        batch += f'Provider: {self.provider.value}\n'
        batch += f'Status: {self.status.value}'
        return batch

    @classmethod
    def from_provider(
        cls,
        provider: LLMProvider,
        provider_id: str,
    ) -> Self:
        """Create a new batch from provider components, generating a new ID automatically."""
        return cls(
            id=ExtractionBatchId.generate_new(),
            provider=provider,
            provider_id=provider_id,
            status=BatchStatus.SUBMITTED,
        )


@dataclass(frozen=True)
class BatchCursor:
    """Cursor for keyset pagination of extraction batches inside the staging DB."""

    created_at: int
    batch_id: bytes
