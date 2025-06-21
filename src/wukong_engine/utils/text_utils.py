import re

from nltk.corpus import stopwords
from unidecode import unidecode

from wukong_engine.data_model import DataModel


def normalize_text(text: str) -> str:
    """Normalize text to a simpler representation

    Args:
        text: _description_

    Returns:
        _description_
    """
    language = DataModel().parameters.get('output_language', 'english')  # Get language
    stop_words = stopwords.words(language)  # Remove language-specific stop words
    relevant_text = ' '.join([word for word in text.lower().split() if word not in stop_words])
    simple_text = unidecode(relevant_text.replace('¬', '').replace('°', ''))  # Remove non-ascii characters
    return ' '.join(re.sub(r'[^a-zA-Z0-9 ]', '', simple_text).split())  # Remove non-alphanumeric characters and return
