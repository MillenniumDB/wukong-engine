"""Port for clearing previously exported knowledge."""

from typing import Protocol


class ExportCleaner(Protocol):
    """Clears the exported knowledge, whatever the format it was exported in."""

    def clear(self, export_uri: str) -> None:
        """Remove every previously exported output.

        Args:
            export_uri: Base location whose previously exported output is removed.
        """
        ...
