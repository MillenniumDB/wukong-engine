"""OpenAI adapter implementing the LLM client port."""

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI, AuthenticationError, RateLimitError
from openai.types.responses import Response as OpenAIResponse
from openai.types.responses import ResponseOutputRefusal
from wukong_engine.app.llm.elements import LLMClient, LLMRequest, LLMResponse
from wukong_engine.app.llm.elements.values import ResponseMetrics
from wukong_engine.app.llm.elements.values.errors import LLMConfigurationError, LLMTransientError
from wukong_engine.app.llm.model import LLMRegistry

from .config import OpenAIConfig


# TODO: Support minimal vs none in reasoning effort
# TODO: Test reasoning effort NONE vs MINIMAL vs LOW vs MEDIUM (for both entity and relationship extraction)
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
            'instructions': request.system_prompt,
            'input': request.user_prompt,
        }

        # TODO: Set reasoning effort if supported by the model
        # 5.4 mini supports 'none', 'low'
        # 5 mini supports 'minimal', 'low'
        if LLMRegistry.is_reasoning_model(model):
            kwargs['reasoning'] = {'effort': 'low'}

        # Include structured response schema if provided
        if request.response_schema is not None:
            kwargs['text'] = {
                'format': {
                    'type': 'json_schema',
                    'name': 'schema',
                    'strict': True,
                    'schema': request.response_schema,
                },
            }

        # Await response, handling errors
        try:
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

        # Return the response in the expected format
        return LLMResponse(
            content=response.output_text,
            model=response.model,
            metrics=ResponseMetrics.from_usage(response.usage.model_dump() if response.usage else {}),
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
