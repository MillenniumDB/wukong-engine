"""Exceptions raised by the knowledge export use cases."""

from wukong_engine.app.shared.exceptions import ApplicationError


class KnowledgeExportError(ApplicationError):
    """Base exception for knowledge export errors."""
