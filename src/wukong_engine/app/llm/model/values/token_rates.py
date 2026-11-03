"""Prices of the tokens of an LLM."""

from dataclasses import dataclass

TOKENS_PER_RATE_UNIT = 1_000_000


@dataclass(frozen=True, slots=True)
class TokenRates:
    """Prices of a model's tokens, in US dollars per million tokens.

    The categories match the ones token usage is recorded in, which don't overlap.

    Attributes:
        input: Price of input tokens that neither read from nor wrote to the cache.
        cached_input: Price of input tokens read from the cache.
        cache_write: Price of input tokens written to the cache.
        output: Price of output tokens, reasoning tokens included, which providers bill as output.
        as_of: Date the prices were taken from the provider's pricing page, in ISO 8601 (YYYY-MM-DD).
        batch_discount: Fraction of every price waived for requests sent in a batch (0.5 for half price).
    """

    input: float
    cached_input: float
    cache_write: float
    output: float
    as_of: str
    batch_discount: float = 0.0

    def cost(
        self,
        *,
        input_tokens: int,
        cached_tokens: int,
        cache_write_tokens: int,
        output_tokens: int,
        batch: bool = False,
    ) -> float:
        """Compute the price of some token usage.

        Args:
            input_tokens: Input tokens that neither read from nor wrote to the cache.
            cached_tokens: Input tokens read from the cache.
            cache_write_tokens: Input tokens written to the cache.
            output_tokens: Output tokens, reasoning tokens included.
            batch: Whether the tokens were used by requests sent in a batch.

        Returns:
            The price, in US dollars.
        """
        full_price = (
            input_tokens * self.input
            + cached_tokens * self.cached_input
            + cache_write_tokens * self.cache_write
            + output_tokens * self.output
        ) / TOKENS_PER_RATE_UNIT
        return full_price * (1 - self.batch_discount) if batch else full_price
