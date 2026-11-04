"""Tests for comparing document registries when documents are added to a workspace."""

from types import MappingProxyType

from wukong_engine.core.documents.model import DocumentCollection, DocumentRegistry, DocumentSource
from wukong_engine.core.documents.model.values import DocumentCollectionName, DocumentSourceMode

MISSIONS = DocumentSource(root='missions', mode=DocumentSourceMode.DIRECTORY)
ARCHIVE = DocumentSource(root='archive', mode=DocumentSourceMode.RECURSIVE)
CREW = DocumentSource(root='crew', mode=DocumentSourceMode.DIRECTORY)


def _registry(**collections: tuple[DocumentSource, ...]) -> DocumentRegistry:
    """Build a registry with a collection of the given sources for each keyword."""
    return DocumentRegistry(
        collections=MappingProxyType(
            {
                DocumentCollectionName(name): DocumentCollection(name=DocumentCollectionName(name), sources=sources)
                for name, sources in collections.items()
            },
        ),
    )


def test_a_registry_adding_collections_and_sources_misses_nothing() -> None:
    """Let another registry add sources to a collection, in any order, and add collections."""
    previous = _registry(missions=(MISSIONS,))

    assert previous.sources_missing_from(_registry(missions=(ARCHIVE, MISSIONS), crew=(CREW,))) == ()


def test_sources_left_out_or_moved_to_another_collection_are_missing() -> None:
    """Report each source another registry drops, including from a collection it renames or removes."""
    previous = _registry(missions=(MISSIONS, ARCHIVE), crew=(CREW,))

    missing = previous.sources_missing_from(_registry(missions=(MISSIONS,), staff=(CREW,)))

    assert missing == ((DocumentCollectionName('missions'), ARCHIVE), (DocumentCollectionName('crew'), CREW))
