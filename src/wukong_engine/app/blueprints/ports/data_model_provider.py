from pathlib import Path
from typing import Protocol

from wukong_engine.core.data_model import DataModel


class DataModelProvider(Protocol):
    """Provides access to a DataModel for application use."""

    def get(self, path: Path) -> DataModel:
        """Get a fully validated DataModel from the given path.

        Raises:
            DataModelLoadError (or a domain-level error) if the model
            cannot be obtained or is invalid.
        """
        ...
