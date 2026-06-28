import asyncio
import itertools
import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable

# Logging
logger = logging.getLogger(__name__)


class ExecutionController:
    """Controls lifecycle of a running concurrent execution."""

    def __init__(self) -> None:
        """Initialize the controller with default state."""
        self._termination_requested = False
        self._termination_error: Exception | None = None

    @property
    def should_stop_scheduling(self) -> bool:
        """Whether new items should stop being scheduled for execution."""
        return self._termination_requested

    @property
    def termination_error(self) -> Exception | None:
        """The error that caused the termination, if any."""
        return self._termination_error

    def request_termination(self, error: Exception | None = None) -> None:
        """Request graceful termination of the execution, providing the error that caused the termination."""
        self._termination_requested = True

        # Set the termination error if it hasn't been set already
        if self._termination_error is None and error is not None:
            self._termination_error = error


class AsyncConcurrentRunner[T, R]:
    """Executes async operations concurrently while supporting graceful draining.

    There is at most `max_concurrency` tasks running concurrently. The runner yields results as they complete.
    If any task raises an exception, the runner will fail fast and propagate the exception immediately.

    Once termination is requested:
    - no new items are scheduled
    - already running tasks are allowed to finish normally
    - the termination error is raised after draining, if requested
    """

    def __init__(self, fn: Callable[[T], Awaitable[R]], max_concurrency: int) -> None:
        """Initialize the runner with an async function and maximum concurrency."""
        # Validate max_concurrency parameter
        if max_concurrency <= 0:
            raise ValueError('max_concurrency must be greater than zero')

        # Components
        self._fn = fn
        self._max_concurrency = max_concurrency
        self._controller: ExecutionController | None = None

    @property
    def controller(self) -> ExecutionController:
        """Access the execution controller for managing termination."""
        if self._controller is None:
            error = 'Async execution controller accessed before runner started'
            logger.error(error)
            raise RuntimeError(error)
        return self._controller

    async def run(self, items: Iterable[T]) -> AsyncIterator[R]:
        """Run the async function concurrently over the provided items, yielding results as they complete."""
        # Initialize the execution controller for this run
        self._controller = ExecutionController()

        # fn: Execute the async callable for a given item
        async def execute(item: T) -> R:
            return await self._fn(item)

        # Create an iterator over the items and a set of active async tasks
        iterator = iter(items)
        active: set[asyncio.Task[R]] = set()

        # fn: Start a new task for the given item and add it to the active set
        def start_task(item: T) -> None:
            task = asyncio.create_task(execute(item))
            active.add(task)

        # Start initial tasks up to the maximum concurrency limit
        for item in itertools.islice(iterator, self._max_concurrency):
            start_task(item)

        # Execute tasks concurrently, yielding results as they complete
        worker_failed = False
        try:
            while active:
                # Wait until one or more completed tasks are available, then remove them from the active set
                done, pending = await asyncio.wait(active, return_when=asyncio.FIRST_COMPLETED)
                active = pending

                # Fail Fast: If any completed task has an exception or was cancelled, raise immediately
                for task in done:
                    if task.cancelled():
                        raise asyncio.CancelledError
                    exception = task.exception()
                    if exception is not None:
                        worker_failed = True
                        raise exception

                # Schedule replacements for completed tasks
                for _ in done:
                    # Graceful Draining: If termination is requested, stop scheduling new tasks
                    if self._controller.should_stop_scheduling:
                        break

                    # Schedule a new task for the next item in the iterator, if available
                    try:
                        item = next(iterator)
                    except StopIteration:
                        break
                    start_task(item)

                # Yield completed results
                for task in done:
                    yield task.result()

        # Cleanup
        finally:
            # If a worker failed, cancel remaining tasks to propagate failure
            if worker_failed:
                for task in active:
                    task.cancel()

            # Gather any remaining tasks to avoid resource leaks
            await asyncio.gather(*active, return_exceptions=True)
            active.clear()

        # Graceful Draining: Raise the termination error if requested
        if self._controller.termination_error:
            raise self._controller.termination_error
