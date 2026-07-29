import shutil
from pathlib import Path


def clear_directory(directory: Path) -> None:
    """Delete all files and subdirectories inside a directory."""
    if not directory.is_dir():
        raise NotADirectoryError(directory)

    for child in directory.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
