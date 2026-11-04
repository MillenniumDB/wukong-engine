"""Use case for checking what adding the documents of a registry to the ingested ones would do."""

import logging
from collections import defaultdict
from collections.abc import Iterable

from wukong_engine.app.document_ingestion.elements import DocumentAdditions
from wukong_engine.app.document_ingestion.ports import DocumentStreamProvider
from wukong_engine.app.document_ingestion.services import DocumentSourceNormalizer
from wukong_engine.app.staging.ports import UnitOfWork
from wukong_engine.core.documents.elements import Document
from wukong_engine.core.documents.model import DocumentRegistry
from wukong_engine.core.documents.model.values import ContextLevel, DocumentCollectionName
from wukong_engine.core.knowledge.model import KnowledgeModel
from wukong_engine.core.knowledge.model.values import EntityTypeName
from wukong_engine.core.shared.identity import ContentHash

# Logging
logger = logging.getLogger(__name__)

type CollectionLink = tuple[EntityTypeName, ContextLevel, DocumentCollectionName]
type ExtractableType = tuple[EntityTypeName, ContextLevel]


class CheckDocumentAdditions:
    """Use case for checking what adding the documents of a registry to the ingested ones would do."""

    def __init__(self, stream_provider: DocumentStreamProvider, uow: UnitOfWork) -> None:
        """Initialize the use case with its dependencies.

        Args:
            stream_provider: Provider that discovers documents from each collection's sources.
            uow: Unit of work used to read the ingested documents and the state of their extractions.
        """
        self._source_normalizer = DocumentSourceNormalizer()
        self._stream_provider = stream_provider
        self._uow = uow

    def execute(self, registry: DocumentRegistry, data_uri: str, knowledge_model: KnowledgeModel) -> DocumentAdditions:
        """Find the documents of a registry, and the ingested ones whose extracted relationships adding them would break.

        Entity extraction links each entity type to its collections, and extracts it from every document of a linked
        collection. A document's relationships are extracted from the entities it has by then, so they would miss the
        entities of any entity type the document becomes extractable for afterwards, by joining another collection or
        by a collection of it being added to an entity type.

        Args:
            registry: Registry whose sources hold the documents to add, along with the ingested ones.
            data_uri: Data root directory the registry's sources are resolved against.
            knowledge_model: Knowledge model whose entity types the documents are extracted for.

        Returns:
            The documents found and how many of them are new, along with the ingested documents that relationships
            were extracted from and that would become extractable for more entity types.
        """
        with self._uow as tx:
            stored_links = tx.entities.get_collection_links()
            extracted = {
                document.id.content: (document, collections)
                for document, collections in tx.extraction.relationships.stream_extracted_documents()
            }

        # Find every document of the registry, and the collections it adds to documents relationships were extracted from
        found: dict[ContentHash, Document] = {}
        added_collections: dict[ContentHash, set[DocumentCollectionName]] = defaultdict(set)
        for collection in registry.collections.values():
            logger.info(f'Looking for documents in collection "{collection.name}"...')
            sources = self._source_normalizer.normalize(collection.sources)
            for document in self._stream_provider.stream(sources, data_uri):
                found[document.id.content] = document
                if document.id.content in extracted:
                    added_collections[document.id.content].add(collection.name)

        with self._uow as tx:
            stored = tx.documents.find_stored_documents(found.values())

        # Links are only ever added, so the stored ones are kept along with those of the model
        types_by_collection = self._types_by_collection(stored_links)
        new_types_by_collection = self._types_by_collection(stored_links | self._model_links(knowledge_model))
        conflicts = tuple(
            document
            for content_id, (document, collections) in extracted.items()
            if not self._types(collections | added_collections.get(content_id, set()), new_types_by_collection)
            <= self._types(collections, types_by_collection)
        )
        return DocumentAdditions(
            found_documents=len(found),
            new_documents=len(found) - len(stored),
            conflicts=conflicts,
        )

    @staticmethod
    def _model_links(knowledge_model: KnowledgeModel) -> frozenset[CollectionLink]:
        """Get the links entity extraction makes between the model's active entity types and their collections.

        Args:
            knowledge_model: Knowledge model whose entity types are linked.

        Returns:
            The entity type, context level and collection of each link.
        """
        return frozenset(
            (entity_type.name, context_level, collection)
            for entity_type in knowledge_model.active_entity_types.values()
            for context_level, collections in entity_type.document_collections.items()
            for collection in collections
        )

    @staticmethod
    def _types_by_collection(
        links: Iterable[CollectionLink],
    ) -> dict[DocumentCollectionName, set[ExtractableType]]:
        """Group links by collection.

        Args:
            links: Links between entity types and collections.

        Returns:
            The entity types, with the context level each is extracted at, that each linked collection is extracted for.
        """
        types: dict[DocumentCollectionName, set[ExtractableType]] = defaultdict(set)
        for entity_type, context_level, collection in links:
            types[collection].add((entity_type, context_level))
        return types

    @staticmethod
    def _types(
        collections: Iterable[DocumentCollectionName],
        types_by_collection: dict[DocumentCollectionName, set[ExtractableType]],
    ) -> set[ExtractableType]:
        """Get the entity types a document of some collections is extracted for.

        Args:
            collections: Collections the document belongs to.
            types_by_collection: Entity types each collection is extracted for.

        Returns:
            The entity types, with the context level each is extracted at, of all the collections.
        """
        return {extractable for collection in collections for extractable in types_by_collection.get(collection, ())}
