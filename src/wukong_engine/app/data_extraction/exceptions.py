from wukong_engine.app.shared.exceptions import ApplicationError


class DataExtractionError(ApplicationError):
    """Base exception for data extraction errors."""


class ExtractionRequestBuildError(DataExtractionError):
    """Error building extraction requests."""


class ExtractionExecutionError(DataExtractionError):
    """Error during extraction execution."""
