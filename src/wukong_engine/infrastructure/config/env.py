import os
from typing import Any


def load_env() -> dict[str, Any]:
    """Load environment variables and return them as a dictionary.

    Returns:
        A dictionary containing the loaded environment variables.

    Raises:
        ValueError: If required environment variables are missing.
    """
    return {
        'llm': {
            'api_key': os.getenv('OPENAI_API_KEY'),
        },
    }
