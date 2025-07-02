import re

from nltk.corpus import stopwords
from unidecode import unidecode

from wukong_engine.core.data_model import DataModel


def normalize_text(text: str) -> str:
    """Normalize the input text to a simplified form.

    Args:
        text: Input text to be normalized.

    Returns:
        Normalized text with stop words and non-alphanumeric characters removed, and converted to lowercase.
    """
    language = DataModel().parameters.get('output_language', 'english').lower()  # Get language
    stop_words = stopwords.words(language)  # Remove language-specific stop words
    relevant_text = ' '.join([word for word in text.lower().split() if word not in stop_words])
    simple_text = unidecode(relevant_text.replace('¬', '').replace('°', ''))  # Remove non-ascii characters
    return ' '.join(re.sub(r'[^a-zA-Z0-9 ]', '', simple_text).split())  # Remove non-alphanumeric characters and return
