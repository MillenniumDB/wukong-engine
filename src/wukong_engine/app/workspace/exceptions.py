"""Exceptions raised when defining or validating a workspace."""

from wukong_engine.app.shared.exceptions import ApplicationError


class WorkspaceError(ApplicationError):
    """Base exception for workspace definition errors."""


class InvalidWorkspaceError(WorkspaceError):
    """Errors validating the workspace structure and contents."""
