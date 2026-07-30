from enum import Enum


class KnowledgeExportFormat(Enum):
    """Export formats for extracted knowledge.

    Attributes:
        MDB: MillenniumDB graph database QM (Quad Model) file.
        NEO4J: Neo4j graph database CSV files.
    """

    # Knowledge Graphs
    MDB = 'MillenniumDB'
    NEO4J = 'Neo4j'
