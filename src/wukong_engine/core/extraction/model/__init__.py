"""The extraction model package.

This package contains schematic components for extraction.
"""

from .prompt_spec import EntityExtractionPromptSpec
from .task import EntityExtractionTask

__all__ = [
    'EntityExtractionPromptSpec',
    'EntityExtractionTask',
]
