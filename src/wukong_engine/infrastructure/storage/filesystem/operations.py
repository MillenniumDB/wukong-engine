"""Filesystem operations for local storage."""

import json
import shutil
import uuid
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any


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


def load_json_file(path: Path) -> Any:
    """Load a JSON file written by a user, such as a workspace definition.

    The file is read as UTF-8, dropping a leading byte order mark that editors may add.

    Args:
        path: Path to the JSON file.

    Returns:
        The parsed JSON contents.

    Raises:
        OSError: If the file cannot be read.
        ValueError: If the file is not valid JSON, or an object in it repeats a key (which plain JSON parsing would
            resolve by silently keeping the last value).
    """
    return json.loads(path.read_text(encoding='utf-8-sig'), object_pairs_hook=_reject_duplicate_keys)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Build a JSON object from its key-value pairs, rejecting repeated keys.

    Args:
        pairs: Key-value pairs of the object, in file order.

    Returns:
        The object as a dictionary.

    Raises:
        ValueError: If a key appears more than once.
    """
    duplicates = sorted(key for key, count in Counter(key for key, _ in pairs).items() if count > 1)
    if duplicates:
        raise ValueError(f'Duplicate keys in a JSON object: {", ".join(duplicates)}')
    return dict(pairs)
