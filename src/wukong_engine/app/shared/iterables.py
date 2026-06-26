from collections.abc import Iterable, Iterator


def batched[T](items: Iterable[T], size: int) -> Iterator[list[T]]:
    """Group items into a stream of batches of specified size."""
    batch: list[T] = []
    for item in items:
        batch.append(item)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch
