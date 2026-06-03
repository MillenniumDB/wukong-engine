"""OpenAI adapter implementing the LLM client port."""

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI, AuthenticationError, RateLimitError
from wukong_engine.app.llm.elements import LLMClient, LLMRequest, LLMResponse
from wukong_engine.app.llm.elements.values.errors import LLMConfigurationError, LLMTransientError

from .config import OpenAIConfig


# TODO: Test happy path with no structured response
# TODO: Test all errors
# TODO: Test structured response
# TODO: Move on to Extraction Executor
class OpenAIClient(LLMClient):
    """Client that executes LLM requests against the OpenAI API."""

    def __init__(self, config: OpenAIConfig) -> None:
        """Initialize the OpenAI client with the given configuration."""
        self._config = config
        self._client = AsyncOpenAI(api_key=config.api_key, timeout=config.timeout, max_retries=config.max_retries)

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a response from the LLM based on the given request."""
        # Base parameters for the API call
        kwargs = {
            'model': request.model or self._config.model,
            'instructions': request.system_prompt,
            'input': request.user_prompt,
        }

        # Include structured response schema if provided
        if request.response_schema is not None:
            kwargs['text'] = {
                'format': {
                    'type': 'json_schema',
                    'strict': True,
                    'schema': request.response_schema,
                },
            }

        # Await response, handling errors
        try:
            response = await self._client.responses.create(**kwargs)
        except AuthenticationError as exc:
            raise LLMConfigurationError('Authentication with the LLM provider failed.') from exc
        except RateLimitError as exc:
            raise LLMTransientError('The LLM provider rate limit was exceeded.') from exc
        except APITimeoutError as exc:
            raise LLMTransientError('The LLM request timed out.') from exc
        except APIConnectionError as exc:
            raise LLMTransientError('Failed to connect to the LLM provider.') from exc
        except APIStatusError as exc:
            raise LLMTransientError('The LLM provider returned an error.') from exc

        # Return the response in the expected format
        return LLMResponse(
            content=response.output_text,
            model=response.model,
            input_tokens=response.usage.input_tokens if response.usage else 0,
            output_tokens=response.usage.output_tokens if response.usage else 0,
        )
