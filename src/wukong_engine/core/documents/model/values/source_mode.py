"""Provides document source modes.

Classes:
    DocumentSourceMode: Enum representing supported document source modes.
"""

from enum import Enum


class DocumentSourceMode(Enum):
    """Supported document source modes.

    Attributes:
        FILE: A single text file.
        DIRECTORY: All the text files in a directory.
        RECURSIVE: All the text files in a directory and its recursive subdirectories.
    """

    FILE = 'file'
    DIRECTORY = 'directory'
    RECURSIVE = 'recursive'
