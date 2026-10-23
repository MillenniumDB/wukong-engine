"""Exceptions raised by the model ingestion application layer."""

from wukong_engine.app.shared.exceptions import ApplicationError


class ModelIngestionError(ApplicationError):
    """Raised when the knowledge model or the document registry can't be loaded or is invalid."""
