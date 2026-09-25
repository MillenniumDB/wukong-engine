"""Base exceptions for the application layer."""


class ApplicationError(Exception):
    """Base exception for application layer errors."""


class PipelineExecutionError(ApplicationError):
    """Error during pipeline execution."""
