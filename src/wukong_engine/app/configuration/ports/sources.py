from pathlib import Path
from typing import Protocol

from wukong_engine.core.schema import DataModel


class DataModelSource(Protocol):
    """Provides a validated DataModel for application use.

    Implementations may load the model from any external source
    (file system, database, remote service, etc.), but must return
    a fully constructed and valid DataModel instance.
    """

    def get(self, path: Path) -> DataModel:
        """Retrieve the DataModel.

        Raises:
            DataModelLoadError (or a domain-level error) if the model
            cannot be obtained or is invalid.
        """
        ...
