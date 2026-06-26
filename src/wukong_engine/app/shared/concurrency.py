import asyncio
import itertools
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable


async def async_map_concurrent[T, R](
    fn: Callable[[T], Awaitable[R]],
    items: Iterable[T],
    max_concurrency: int = 5,
) -> AsyncIterator[R]:
    """Map an async function over items concurrently.

    Executes at most `max_concurrency` tasks at once and yields results as soon as they complete.
    Raises immediately on the first task failure and cancels remaining tasks.
    """
    # Validate max_concurrency parameter
    if max_concurrency <= 0:
        raise ValueError('max_concurrency must be greater than zero')

    # Execute the async callable for a given item
    async def execute(item: T) -> R:
        return await fn(item)

    # Create an iterator over the items and a set of active/all async tasks
    iterator = iter(items)
    active: set[asyncio.Task[R]] = set()
    all_tasks: set[asyncio.Task[R]] = set()

    def start_task(item: T) -> None:
        task = asyncio.create_task(execute(item))
        active.add(task)
        all_tasks.add(task)

    for item in itertools.islice(iterator, max_concurrency):
        start_task(item)

    # Execute tasks concurrently, yielding results as they complete
    try:
        while active:
            done, pending = await asyncio.wait(active, return_when=asyncio.FIRST_COMPLETED)
            active = pending

            # Fail fast: inspect all completed tasks before yielding results
            for task in done:
                if task.cancelled():
                    raise asyncio.CancelledError
                exception = task.exception()
                if exception is not None:
                    raise exception

            # Yield successful results and refill the concurrency window
            for task in done:
                yield task.result()
                try:
                    item = next(iterator)
                except StopIteration:
                    continue
                start_task(item)

    # Cancel any remaining tasks to avoid resource leaks
    finally:
        for task in all_tasks:
            if not task.done():
                task.cancel()
        if all_tasks:
            await asyncio.gather(*all_tasks, return_exceptions=True)
