"""OpenAI adapter implementing the LLM client port."""

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI, AuthenticationError, RateLimitError
from openai.types.responses import Response as OpenAIResponse
from openai.types.responses import ResponseOutputRefusal
from wukong_engine.app.config.llm import LLMRegistry
from wukong_engine.app.llm.elements import LLMClient, LLMRequest, LLMResponse
from wukong_engine.app.llm.elements.values import LLMResponseMetrics
from wukong_engine.app.llm.elements.values.errors import LLMConfigurationError, LLMError, LLMTransientError

from .config import OpenAIConfig


class OpenAIClient(LLMClient):
    """Client that executes LLM requests against the OpenAI API."""

    def __init__(self, config: OpenAIConfig) -> None:
        """Initialize the OpenAI client with the given configuration."""
        self._config = config
        self._client = AsyncOpenAI(api_key=config.api_key, timeout=config.timeout, max_retries=config.max_retries)

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a response from the LLM based on the given request."""
        # Base parameters for the API call
        model = request.model if request.model is not None else self._config.model
        kwargs = {
            'model': model.name,
            'instructions': request.prompt.instructions,
            'input': request.prompt.content,
        }

        # Set reasoning effort if supported by the model
        reasoning_effort = (
            request.reasoning_effort
            if request.reasoning_effort is not None
            else LLMRegistry.get_reasoning_effort(model)
        )
        if LLMRegistry.is_reasoning_model(model) and reasoning_effort is not None:
            kwargs['reasoning'] = {'effort': reasoning_effort.value}

        # Set temperature if supported by the model
        temperature = request.temperature if request.temperature is not None else 0.0
        if LLMRegistry.is_supported_model(model) and not LLMRegistry.is_reasoning_model(model):
            kwargs['temperature'] = temperature

        # Include structured response schema if provided
        schema = request.prompt.schema
        if schema is not None:
            kwargs['text'] = {
                'format': {
                    'type': 'json_schema',
                    'name': 'schema',
                    'strict': True,
                    'schema': schema,
                },
            }

        # Await response, handling errors
        try:
            # TODO: Remove after testing
            return LLMResponse(content='', model='', metrics=LLMResponseMetrics())  # Placeholder response for testing
            response: OpenAIResponse = await self._client.responses.create(**kwargs)
            self._ensure_successful_response(response)
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
        except Exception as exc:
            raise LLMError('An unexpected error occurred while interacting with the LLM provider.') from exc

        # Return the response in the expected format
        return LLMResponse(
            content=response.output_text,
            model=response.model,
            metrics=LLMResponseMetrics.from_usage(response.usage.model_dump() if response.usage else {}),
        )

    def _ensure_successful_response(self, response: OpenAIResponse) -> None:
        """Ensure the LLM response indicates a successful generation."""
        # Incomplete response
        if response.status != 'completed':
            raise LLMTransientError(f'The LLM response status was {response.status}, indicating a generation failure.')

        # Refusal (if the model refused to generate a response, e.g. due to content moderation)
        refusal_item: ResponseOutputRefusal | None = next(
            (item for item in response.output if isinstance(item, ResponseOutputRefusal)),
            None,
        )
        if refusal_item is not None:
            raise LLMTransientError('The LLM refused to generate a response.')
