from pathlib import Path
from typing import Protocol

from wukong_engine.app.model_ingestion.dtos import CreateGraphModelCommand


class GraphModelSchemaProvider(Protocol):
    """Provides access to a user-defined schema that can be used to create a GraphModel."""

    def get(self, path: Path) -> CreateGraphModelCommand:
        """Get a fully validated GraphModel schema from the given path.

        Raises:
            GraphModelLoadError (or a domain-level error) if the model
            cannot be obtained or is invalid.
        """
        ...
