"""Exceptions raised by the document ingestion application layer."""

from wukong_engine.app.shared.exceptions import ApplicationError


class DocumentIngestionError(ApplicationError):
    """Base exception for document ingestion errors."""
