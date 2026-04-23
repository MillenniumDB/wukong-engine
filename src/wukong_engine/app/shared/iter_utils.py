from collections.abc import Iterable, Iterator


def batched[T](iterable: Iterable[T], size: int) -> Iterator[list[T]]:
    """Batch an iterable into lists of a specified size."""
    batch: list[T] = []
    for item in iterable:
        batch.append(item)
        if len(batch) == size:
            yield batch
            batch = []

    if batch:
        yield batch
