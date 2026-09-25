"""TOML file loading for configuration."""

import tomllib
from pathlib import Path
from typing import Any


def load_toml(path: Path) -> dict[str, Any]:
    """Load a TOML file and return its contents as a dictionary.

    Args:
        path: Path to the TOML file.

    Returns:
        The parsed TOML contents.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If the file cannot be read or is not valid TOML.
    """
    try:
        with path.open('rb') as f:
            return tomllib.load(f)
    except FileNotFoundError as error:
        raise FileNotFoundError(f'Configuration file "{path}" not found') from error
    except OSError as error:
        raise ValueError(f'Failed to read configuration file "{path}"') from error
    except tomllib.TOMLDecodeError as error:
        raise ValueError(f'Invalid structure for the configuration in "{path}"') from error
