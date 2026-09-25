"""Jobs for data extraction."""

from dataclasses import dataclass
from typing import Self

from wukong_engine.core.documents.elements import ContextRef
from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.shared.identity import ContentHash

from .values import ExtractionJobId

# Constants
MAX_FAILED_ATTEMPTS = 3  # Maximum number of failed attempts before marking as failed


@dataclass(frozen=True, slots=True)
class ExtractionJob:
    """Job for data extraction from a specific source.

    Attributes:
        id: Unique identifier of the job.
        context_ref: Reference to the source context (level and content ID) the job extracts from.
    """

    id: ExtractionJobId
    context_ref: ContextRef

    @classmethod
    def from_context(
        cls,
        level: ContextLevel,
        content_id: ContentHash,
    ) -> Self:
        """Create a new job from its extraction context components, generating a new ID automatically.

        Args:
            level: Context level of the source (e.g. document or chunk).
            content_id: Content hash identifying the source.

        Returns:
            A new job referencing the given source context.
        """
        return cls(id=ExtractionJobId.generate_new(), context_ref=ContextRef(level, content_id))
