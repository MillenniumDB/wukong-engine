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
    data_model = DataModel()  # Get data model
    language = data_model.parameters.get('output_language', 'english')
    stop_words = stopwords.words(language)  # Remove language-specific stop words
    relevant_text = ' '.join([word for word in text.lower().split() if word not in stop_words])
    simple_text = unidecode(relevant_text.replace('¬', '').replace('°', ''))  # Remove non-ascii characters
    normalized_text = ' '.join(re.sub(r'[^a-zA-Z0-9 ]', '', simple_text).split())  # Remove non-alphanumeric characters
    return normalized_text


def remove_sentence_dot(sentence: str) -> str:
    """Remove the dot at the end of a sentence

    Args:
        sentence: _description_

    Returns:
        _description_
    """
    return sentence[:-1] if sentence.endswith('.') else sentence
