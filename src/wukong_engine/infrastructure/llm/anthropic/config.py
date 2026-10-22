"""Configuration for the Anthropic LLM client."""

from dataclasses import dataclass, field

from wukong_engine.app.llm.elements.values import ReasoningEffort
from wukong_engine.app.llm.model import LLM, LLMRegistry
from wukong_engine.app.llm.model.values import LLMProvider

# Constants
MIN_ALLOWED_TIMEOUT = 30  # Minimum allowed timeout in seconds
MAX_ALLOWED_TIMEOUT = 300  # Maximum allowed timeout in seconds
MAX_ALLOWED_RETRIES = 5  # Maximum allowed retries
SUPPORTED_EFFORTS = frozenset(
    {'none', 'low', 'medium', 'high', 'xhigh', 'max'}
)  # API levels, plus "none" (no thinking)
THINKING_OPTIONAL_MODELS = frozenset({'claude-haiku-5-5'})  # Models accepting disabled thinking (e.g. not Sonnet 5.5)


@dataclass(frozen=True, slots=True)
class AnthropicConfig:
    """Configuration parameters for the Anthropic client.

    Attributes:
        api_key: Anthropic API key used to authenticate requests.
        model: LLM used for requests; defaults to the registry's default Anthropic model, which is enough for clients
            that only manage already submitted batches.
        max_output_tokens: Maximum number of tokens the model may generate per response, including thinking.
        timeout: Request timeout in seconds.
        max_retries: Number of retries the Anthropic SDK performs on failed requests.
    """

    api_key: str
    model: LLM = field(default_factory=lambda: LLMRegistry.default_model(LLMProvider.ANTHROPIC))
    max_output_tokens: int = 16000  # Default: 16000 tokens, the recommended ceiling for non-streaming requests
    timeout: float = 120  # Default: 2 minutes, more than reasonable for extraction tasks
    max_retries: int = 2  # Default: 2 retries, enough for transient provider issues

    def __post_init__(self) -> None:
        """Validate the configuration invariants.

        Raises:
            ValueError: If the timeout or the number of retries is out of range, or the model's reasoning efforts are
                not supported by the API.
        """
        self._validate_config()
        self._validate_reasoning_efforts()

    def _validate_config(self) -> None:
        """Validate the parameters of the configuration.

        Raises:
            ValueError: If ``timeout`` is outside the allowed range or ``max_retries`` is negative or above the
                allowed maximum.
        """
        if self.timeout < MIN_ALLOWED_TIMEOUT or self.timeout > MAX_ALLOWED_TIMEOUT:
            raise ValueError(f'timeout must be between {MIN_ALLOWED_TIMEOUT} and {MAX_ALLOWED_TIMEOUT} seconds')
        if self.max_retries < 0 or self.max_retries > MAX_ALLOWED_RETRIES:
            raise ValueError(f'max_retries must be greater than or equal to 0 and at most {MAX_ALLOWED_RETRIES}')

    def _validate_reasoning_efforts(self) -> None:
        """Validate that every reasoning effort the registry can produce for the model is supported by the API.

        Raises:
            ValueError: If an effort is not an API level, or is "none" for a model that can't disable thinking.
        """
        if not LLMRegistry.is_reasoning_model(self.model):
            return
        efforts = {LLMRegistry.reasoning_effort(self.model, level) for level in ReasoningEffort}
        for effort in efforts - {None}:
            if effort not in SUPPORTED_EFFORTS:
                raise ValueError(f'Reasoning effort "{effort}" of model "{self.model.name}" is not supported')
            if effort == 'none' and self.model.name not in THINKING_OPTIONAL_MODELS:
                raise ValueError(
                    f'Model "{self.model.name}" maps a reasoning effort to "none", but cannot disable thinking'
                )
