import tomllib
from pathlib import Path
from typing import Any


def load_toml(path: Path) -> dict[str, Any]:
    """Load a TOML file and return its contents as a dictionary."""
    try:
        with path.open('rb') as f:
            return tomllib.load(f)
    except FileNotFoundError as error:
        raise FileNotFoundError(f'Configuration file "{path}" not found') from error
    except OSError as error:
        raise ValueError(f'Failed to read configuration file "{path}"') from error
    except tomllib.TOMLDecodeError as error:
        raise ValueError(f'Invalid structure for the configuration in "{path}"') from error
