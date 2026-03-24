from enum import Enum


class PipelineStep(Enum):
    """Pipeline steps used by the engine.

    Attributes:
        EXTRACT_ENTITIES: Extract entities from documents.
        EXTRACT_RELATIONSHIPS: Extract relationships between entities.
        EXPORT_GRAPH: Export the knowledge graph.
    """

    EXTRACT_ENTITIES = 'extract_entities'
    EXTRACT_RELATIONSHIPS = 'extract_relationships'
    EXPORT_GRAPH = 'export_graph'
