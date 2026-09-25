"""Batches for data extraction."""

from dataclasses import dataclass
from typing import Self

from wukong_engine.app.llm.model.values import LLMProvider

from .values import BatchStatus, ExtractionBatchId


@dataclass(frozen=True, slots=True)
class ExtractionBatch:
    """Batch of extraction jobs for processing.

    Attributes:
        id: Internal identifier of the batch.
        provider: LLM provider the batch was submitted to.
        provider_id: Identifier assigned to the batch by the provider.
        status: Current processing status of the batch.
        created_at: Creation time in epoch milliseconds, as stored in the staging DB. None for batches not yet
            loaded from the store.
    """

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
        """Create a new batch from provider components, generating a new ID automatically.

        The batch starts in the ``SUBMITTED`` status.

        Args:
            provider: LLM provider the batch was submitted to.
            provider_id: Identifier assigned to the batch by the provider.

        Returns:
            A new submitted batch with a freshly generated ID.
        """
        return cls(
            id=ExtractionBatchId.generate_new(),
            provider=provider,
            provider_id=provider_id,
            status=BatchStatus.SUBMITTED,
        )


@dataclass(frozen=True, slots=True)
class BatchCursor:
    """Cursor for keyset pagination of extraction batches inside the staging DB.

    Attributes:
        created_at: Creation time (epoch milliseconds) of the last batch seen.
        batch_id: Raw bytes of the last batch's ID, used to break ties on ``created_at``.
    """

    created_at: int
    batch_id: bytes
