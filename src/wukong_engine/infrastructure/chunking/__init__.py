"""The document chunking package."""

from .config import ChunkingConfig
from .recursive_chunker import RecursiveDocumentChunker

__all__ = [
    'ChunkingConfig',
    'RecursiveDocumentChunker',
]
