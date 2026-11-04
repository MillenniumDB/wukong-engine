"""What adding the documents of a registry to a workspace's ingested ones would do."""

from dataclasses import dataclass

from wukong_engine.core.documents.elements import Document


@dataclass(frozen=True, slots=True)
class DocumentAdditions:
    """What adding the documents of a registry to a workspace's ingested ones would do.

    Attributes:
        found_documents: Unique documents found in the registry's sources.
        new_documents: Documents found that aren't ingested yet.
        conflicts: Ingested documents that relationships were already extracted from, which the registry or the
            knowledge model would make extractable for more entity types. Their relationships would miss the new
            entities, so the addition must not go ahead while there are any.
    """

    found_documents: int
    new_documents: int
    conflicts: tuple[Document, ...]
