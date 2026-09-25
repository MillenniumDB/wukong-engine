"""Helpers for working with iterables."""

from collections.abc import Iterable, Iterator


def batched[T](items: Iterable[T], size: int) -> Iterator[list[T]]:
    """Group items into a stream of batches of specified size.

    Args:
        items: Items to group. Consumed lazily.
        size: Number of items per batch.

    Yields:
        Lists of ``size`` items each, except for the last one, which holds the remaining items.
    """
    batch: list[T] = []
    for item in items:
        batch.append(item)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch
