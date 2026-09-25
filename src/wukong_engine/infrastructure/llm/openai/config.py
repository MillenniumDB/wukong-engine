"""Configuration for the OpenAI LLM client."""

from dataclasses import dataclass, field

from wukong_engine.app.llm.model import LLM, LLMRegistry

# Constants
MIN_ALLOWED_TIMEOUT = 30  # Minimum allowed timeout in seconds
MAX_ALLOWED_TIMEOUT = 300  # Maximum allowed timeout in seconds
MAX_ALLOWED_RETRIES = 5  # Maximum allowed retries


@dataclass(frozen=True, slots=True)
class OpenAIConfig:
    """Configuration parameters for the OpenAI client.

    Attributes:
        api_key: OpenAI API key used to authenticate requests.
        model: LLM used for requests; defaults to the registry's default model.
        max_output_tokens: Maximum number of tokens the model may generate per response.
        timeout: Request timeout in seconds.
        max_retries: Number of retries the OpenAI SDK performs on failed requests.
    """

    api_key: str
    model: LLM = field(default_factory=LLMRegistry.default_model)
    max_output_tokens: int = 32768  # Default: 32768 tokens, the limit for gpt-4.1-mini
    timeout: float = 120  # Default: 2 minutes, more than reasonable for extraction tasks
    max_retries: int = 2  # Default: 2 retries, enough for transient provider issues

    def __post_init__(self) -> None:
        """Validate the configuration invariants.

        Raises:
            ValueError: If the timeout or the number of retries is out of range.
        """
        self._validate_config()

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
