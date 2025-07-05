import json
import logging
import random
import threading
import time
from typing import Any

from openai import OpenAI, OpenAIError

from wukong_engine.config.config import Config

# Logging
logger = logging.getLogger(__name__)

# Configuration
LLM_MODEL = 'gpt-4.1-mini'  # Best model for price/performance ratio
MAX_RETRIES = 5  # Maximum number of retries for LLM API calls
TEMPERATURE = 0.0  # Temperature for the LLM (0.0 for a more deterministic output)


class OpenAIClientProvider:
    """Client provider that manages a singleton instance of the OpenAI client.

    Attributes:
        _instance: Class attribute. The singleton instance of the OpenAI client.
        _lock: Class attribute. A threading lock to ensure thread-safety when creating the singleton instance.
    """

    _instance: OpenAI | None = None
    _lock: threading.Lock = threading.Lock()

    @classmethod
    def get_client(cls) -> OpenAI:
        """Get the singleton instance of the OpenAI client.

        Checks if the client instance already exists, in which case it's returned.
        If it doesn't exist, it creates a new instance (with thread-safety)
        and stores it in the `_instance` class attribute before returning it.

        Returns:
            The singleton instance of the OpenAI client.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = OpenAI(api_key=Config().get_env('OPENAI_API_KEY'))
        return cls._instance


def process_prompt(prompt_data: dict[str, Any]) -> dict[str, Any]:
    """Process a prompt using the OpenAI LLM API.

    Sends a request to the OpenAI LLM API with the provided prompt data,
    handles retries using exponential backoff in case of failure,
    and returns the response in a structured format.

    Args:
        prompt_data: A dictionary containing the prompt data, which includes:
            - `object_name`: The name of the entity/relation type for which the prompt is being processed.
            - `document_name`: The name of the document associated with the prompt.
            - `system_role`: The system role message for the LLM, setting the context and instructions.
            - `user_role`: The user role message for the LLM, containing the information to be processed.

    Returns:
        A dictionary containing the original prompt data and the response from the LLM API.
        The response is structured as a JSON object if it's valid, or as an empty list if it could not be decoded
        or the amount of retries for the LLM API calls exceeded the maximum allowed.
    """
    # Get OpenAI client
    client = OpenAIClientProvider.get_client()

    # Settings for retrying LLM API calls
    retries = 0  # Retry counter
    delay = 1  # Initial delay before retrying (in seconds)
    exponential_base = 2  # Base for exponential backoff

    # Process prompt with the LLM API, with a maximum number of retries
    logger.info(
        f'Processing prompt for type "{prompt_data["object_name"]}" and document "{prompt_data["document_name"]}"',
    )
    result = prompt_data
    response = None
    while response is None:
        try:
            # Send request to the LLM API
            completion = client.chat.completions.create(
                model=LLM_MODEL,
                temperature=TEMPERATURE,
                response_format={'type': 'json_object'},
                messages=[
                    {'role': 'system', 'content': prompt_data['system_role']},
                    {'role': 'user', 'content': prompt_data['user_role']},
                ],
            )

            # Response from the LLM API
            response = completion.choices[0].message.content
            if response is not None:
                break
            logger.error('LLM API call returned "None".')
        except OpenAIError as error:  # Catch specific OpenAI API errors
            logger.error(f'LLM API call failed. Reason: {error}.')
        except Exception:  # Catch unknown errors
            logger.exception('An unexpected error occurred during the LLM API call.')

        # If maximum retries reached, return an empty response
        retries += 1
        if retries > MAX_RETRIES:
            logger.error('Maximum retries reached. Returning empty response.')
            result['response'] = []
            return result

        # Retry using exponential backoff
        time.sleep(delay)
        delay *= exponential_base * (1 + random.random())  # noqa: S311
        logger.info('Retrying LLM API call...')

    # Load and return response
    try:
        result['response'] = json.loads(response)
    except json.JSONDecodeError as error:  # Return empty response if decoding fails
        logger.error(f'LLM API response decoding failed. Reason: {error}. Returning empty response.')
        result['response'] = []
    return result
