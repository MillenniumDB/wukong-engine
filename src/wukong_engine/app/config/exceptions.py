"""Exceptions raised for invalid configuration."""

from wukong_engine.app.shared.exceptions import ApplicationError


class ConfigurationError(ApplicationError):
    """Base exception for configuration errors."""
