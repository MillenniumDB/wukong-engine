"""Extraction Executor."""

from collections.abc import AsyncIterator, Iterable

from wukong_engine.app.data_extraction.dtos import ExtractionRequest, ExtractionResult
from wukong_engine.app.data_extraction.ports import PKNormalizer
from wukong_engine.app.llm.elements import LLMClient

from .prompt_renderer import PromptRenderer


# TODO: Handle extraction errors for LLMClient
# TODO: Parse LLMResponse -> If bad JSON, maybe retry 1 or 2 times max before giving up
# TODO: Return ExtractionResults
# TODO: Async semaphores for concurrency
class ExtractionExecutor:
    """Asynchronous executor for data extraction jobs."""

    def __init__(self, llm_client: LLMClient, pk_normalizer: PKNormalizer) -> None:
        """Initialize the executor with necessary dependencies."""
        self._prompt_renderer = PromptRenderer()
        self._llm_client = llm_client
        self._pk_normalizer = pk_normalizer

    async def execute(self, extraction: ExtractionRequest) -> ExtractionResult:
        """Execute an extraction request."""
        request = self._prompt_renderer.render(extraction.context)
        print(f'PROMPT: {request.user_prompt}')
        print(f'SCHEMA: {request.response_schema}')
        # response = await self._llm_client.generate(request)
        # print(f'CONTENT: {response.content}')
        # print(f'MODEL: {response.model}')
        # print(f'INPUT TOKENS: {response.input_tokens}')
        # print(f'OUTPUT TOKENS: {response.output_tokens}')
        return ExtractionResult(extraction.job, {})

    async def execute_many(self, requests: Iterable[ExtractionRequest]) -> AsyncIterator[ExtractionResult]:
        """Execute multiple extraction jobs."""
        # async with semaphore:
        #     response = await self._llm_client.generate(...)
        for request in requests:
            yield ExtractionResult(request.job, {})
