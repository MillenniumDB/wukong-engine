"""Provides language options for data extraction.

Classes:
    Language: Enum representing available languages for data extraction.
"""

from enum import Enum


class Language(Enum):
    """Languages available for data extraction.

    Attributes:
        EN: English.
        ES: Spanish.
    """

    EN = 'English'
    ES = 'Spanish'
