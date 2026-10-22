"""Exceptions for data extraction."""

from wukong_engine.app.shared.exceptions import ApplicationError


class DataExtractionError(ApplicationError):
    """Base exception for data extraction errors."""


class ExtractionRequestBuildError(DataExtractionError):
    """Error building extraction requests."""


class ExtractionExecutionError(DataExtractionError):
    """Error during extraction execution."""


class ExtractionResultError(DataExtractionError):
    """Error materializing an extraction result whose structure doesn't match the expected response."""
