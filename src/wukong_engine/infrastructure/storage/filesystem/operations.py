"""Filesystem operations for local storage."""

import shutil
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


def clear_directory(directory: Path) -> None:
    """Delete all files and subdirectories inside a directory.

    The directory itself is kept.

    Args:
        directory: Directory to empty.

    Raises:
        NotADirectoryError: If the path is not an existing directory.
    """
    if not directory.is_dir():
        raise NotADirectoryError(directory)

    for child in directory.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


@contextmanager
def replacing_directory(target: Path) -> Iterator[Path]:
    """Build the new contents of a directory aside, replacing the directory with them only if the build succeeds.

    The contents are written into an empty hidden sibling directory, so a failed build leaves the current directory
    untouched, and a successful one leaves no file from the previous contents behind.

    Args:
        target: Directory to replace. It doesn't need to exist yet.

    Yields:
        The empty directory to write the new contents into.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.with_name(f'.{target.name}.{uuid.uuid4().hex}.tmp')
    staging.mkdir()
    try:
        yield staging
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    # A directory can't be renamed over a non-empty one, so the current one is moved aside first
    if target.exists():
        previous = target.with_name(f'.{target.name}.{uuid.uuid4().hex}.old')
        target.rename(previous)
        staging.rename(target)
        shutil.rmtree(previous)
    else:
        staging.rename(target)
