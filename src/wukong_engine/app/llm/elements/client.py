"""Client port for LLM interactions."""

from collections.abc import Iterable
from typing import Protocol

from .request import LLMRequest
from .response import LLMBatchCreationResponse, LLMBatchResult, LLMResponse


class LLMClient(Protocol):
    """Large Language Model (LLM) client."""

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a response from the LLM based on the given request.

        Args:
            request: Rendered request to send to the LLM.

        Returns:
            The LLM response, with its content, the model that produced it and usage metrics.

        Raises:
            LLMResponseError: If the response is incomplete or the LLM refused to generate it.
            LLMConfigurationError: If the client is misconfigured or the provider rejects the request as invalid.
            LLMTransientError: If the provider fails in a way that may succeed on retry (rate limits, timeouts,
                connection or server-side errors).
            LLMInternalError: If an unexpected error occurs within the client or provider.
        """
        ...

    async def create_batch(self, requests: Iterable[LLMRequest], job_ids: Iterable[str]) -> LLMBatchCreationResponse:
        """Create a batch for asynchronous request processing.

        Args:
            requests: Rendered requests to include in the batch.
            job_ids: Identifiers of the jobs each request belongs to, in the same order as ``requests``. They are used
                to match batch results back to their jobs.

        Returns:
            The creation response, with the provider's batch identifier.

        Raises:
            LLMConfigurationError: If the client is misconfigured or the provider rejects the request as invalid.
            LLMTransientError: If the provider fails in a way that may succeed on retry (rate limits, timeouts,
                connection or server-side errors).
            LLMInternalError: If an unexpected error occurs within the client or provider.
        """
        ...

    async def get_batch_status(self, batch_id: str) -> str:
        """Get the current status of a batch.

        Args:
            batch_id: Provider identifier of the batch.

        Returns:
            The provider's status name for the batch.

        Raises:
            LLMConfigurationError: If the client is misconfigured or the provider rejects the request as invalid.
            LLMTransientError: If the provider fails in a way that may succeed on retry (rate limits, timeouts,
                connection or server-side errors).
            LLMInternalError: If an unexpected error occurs within the client or provider.
        """
        ...

    async def get_batch_results(self, batch_id: str) -> tuple[LLMBatchResult, ...]:
        """Get the results of a completed batch.

        Args:
            batch_id: Provider identifier of the batch.

        Returns:
            One result per request that can be matched to a job, holding either its response or an error.

        Raises:
            LLMResponseError: If the batch isn't completed yet.
            LLMConfigurationError: If the client is misconfigured or the provider rejects the request as invalid.
            LLMTransientError: If the provider fails in a way that may succeed on retry (rate limits, timeouts,
                connection or server-side errors).
            LLMInternalError: If an unexpected error occurs within the client or provider.
        """
        ...
