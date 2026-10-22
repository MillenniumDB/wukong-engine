"""Supported output formats for knowledge export."""

from enum import Enum


class KnowledgeExportFormat(Enum):
    """Export formats for extracted knowledge.

    Attributes:
        MDB: QM (Quad Model) graph file.
        NEO4J: Neo4j graph database CSV files.
    """

    # Knowledge Graphs
    MDB = 'QM'
    NEO4J = 'Neo4j'
