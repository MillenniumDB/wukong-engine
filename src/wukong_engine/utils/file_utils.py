import json
import logging
import shutil
from pathlib import Path
from typing import Any

# Logging
logger = logging.getLogger(__name__)


def load_text_data(file_path: Path) -> str:
    """
    Load text data from a specified file.

    Args:
        file_path (Path): The path to the text file.
    Returns:
        str | None: The content of the file as a string, or None if the file does not exist or an error occurs.
    """
    try:
        if file_path.exists():
            return file_path.read_text(encoding='utf-8')
        logger.error(f'Cannot load text data. The file "{file_path}" does not exist.')
    except Exception:
        logger.exception(f'An unexpected error occurred while loading text data from file "{file_path}".')
    return ''


def load_json_data(file_path: Path) -> Any:
    """
    Load JSON data from a specified file.
    """
    try:
        if file_path.exists():
            return json.loads(file_path.read_text(encoding='utf-8'))
        logger.error(f'Cannot load JSON data. The file "{file_path}" does not exist.')
    except Exception:
        logger.exception(f'An unexpected error occurred while loading JSON data from file "{file_path}".')
    return None


def save_text_data(data: str, file_path: Path, mode: str = 'w') -> None:
    """
    Save text data to a specified file.
    """
    try:
        if file_path.parent.exists():
            with file_path.open(mode, encoding='utf-8') as file:
                file.write(data)
        else:
            logger.error(f'The file "{file_path}" has an invalid path and cannot be saved.')
    except Exception:
        logger.exception(f'An unexpected error occurred while saving text data to file "{file_path}".')


def save_json_data(data: Any, file_path: Path) -> None:
    """
    Save JSON data to a specified file.
    """
    try:
        if file_path.parent.exists():
            with file_path.open('w', encoding='utf-8') as file:
                json.dump(data, file, indent=4, ensure_ascii=False)
        else:
            logger.error(f'The file "{file_path}" has an invalid path and cannot be saved.')
    except Exception:
        logger.exception(f'An unexpected error occurred while saving JSON data to file "{file_path}".')


def delete_dir_contents(dir_path: Path, items_to_keep: list[str] | None = None) -> None:
    """
    Delete all contents (files and directories) within a specified directory.
    """
    try:
        if not dir_path.exists():
            logger.error(f'Cannot delete the contents. The directory "{dir_path}" does not exist.')
            return
        if items_to_keep is None:
            items_to_keep = []
        for item in dir_path.iterdir():
            if item.name in items_to_keep:
                continue
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
    except Exception:
        logger.exception(f'An unexpected error occurred while deleting the contents of directory "{dir_path}".')
