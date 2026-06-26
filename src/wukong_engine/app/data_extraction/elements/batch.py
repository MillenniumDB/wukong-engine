"""Batches for data extraction."""

from dataclasses import dataclass
from typing import Self

from wukong_engine.app.llm.model.values import LLMProvider

from .values import BatchStatus, ExtractionBatchId


# TODO: See whats actually needed here later
@dataclass(frozen=True)
class ExtractionBatch:
    """Batch of extraction jobs for processing."""

    id: ExtractionBatchId
    provider: LLMProvider
    provider_id: str
    status: BatchStatus
    provider_status: str | None = None
    error: str | None = None

    def __str__(self) -> str:
        """User-friendly string representation of the extraction batch."""
        batch = f'Batch ID: {self.id}, Provider Batch ID: {self.provider_id}\n'
        batch += f'Provider: {self.provider}\n'
        batch += f'Status: {self.status.value}, Provider Status: {self.provider_status}'
        return batch

    @classmethod
    def from_provider(
        cls,
        provider: LLMProvider,
        provider_id: str,
        provider_status: str | None = None,
    ) -> Self:
        """Create a new batch from provider components, generating a new ID automatically."""
        batch_id = ExtractionBatchId.generate_new()
        return cls(
            id=batch_id,
            provider=provider,
            provider_id=provider_id,
            status=BatchStatus.SUBMITTED,
            provider_status=provider_status,
        )
