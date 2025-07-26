"""Provides utilities for text processing.

This module defines helper functions to handle common
text processing tasks.

Functions:
    normalize_text: Normalizes input text to a more standard form.
"""

import re

from nltk.corpus import stopwords
from unidecode import unidecode

from wukong_engine.core.data_model import DataModel


def normalize_text(text: str) -> str:
    """Normalize the input text to a more standard form.

    Removes stop words, non-ascii/non-alphanumeric characters, and converts the text to lowercase.

    Args:
        text: The input text to be normalized.

    Returns:
        The normalized text.
    """
    language = DataModel().parameters.get('output_language', 'english').lower()  # Get language
    stop_words = stopwords.words(language)  # Remove language-specific stop words
    relevant_text = ' '.join([word for word in text.lower().split() if word not in stop_words])
    simple_text = unidecode(relevant_text.replace('¬', '').replace('°', ''))  # Remove non-ascii characters
    return ' '.join(re.sub(r'[^a-zA-Z0-9 ]', '', simple_text).split())  # Remove non-alphanumeric characters and return
