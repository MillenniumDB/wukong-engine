"""Tests for the Neo4j bulk-import CSV exporter."""

import csv
from pathlib import Path

from wukong_engine.core.documents.elements import Chunk
from wukong_engine.core.documents.elements.values import ChunkId, DocumentId
from wukong_engine.core.shared.identity import ContentHash, InstanceId
from wukong_engine.infrastructure.export.graph.neo4j import Neo4jChunkWriter


def test_strings_are_written_raw_for_the_csv_quoting_to_carry(tmp_path: Path) -> None:
    """Write string values unescaped, since ``neo4j-admin import`` doesn't decode backslash escapes."""
    content = 'First line, with "quotes"\nSecond line at C:\\dir\twith a tab'
    document_id = DocumentId.from_components(InstanceId.generate(), ContentHash.from_content_string('document'))
    chunk = Chunk(
        id=ChunkId.from_components(InstanceId.generate(), ContentHash.from_content_string('chunk')),
        document_id=document_id,
        chunk_index=0,
        start_offset=0,
        end_offset=len(content),
        content=content,
    )
    path = tmp_path / 'Chunk.csv'

    with Neo4jChunkWriter(path) as writer:
        writer.write(chunk)

    with path.open(newline='', encoding='utf-8') as file:
        header, row = list(csv.reader(file))
    assert row[[column.split(':')[0] for column in header].index('content')] == content
