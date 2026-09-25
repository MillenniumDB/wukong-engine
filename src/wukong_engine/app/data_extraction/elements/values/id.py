"""Identifiers for extraction jobs and batches."""

from dataclasses import dataclass
from typing import Self

from wukong_engine.core.shared.identity import InstanceId


@dataclass(frozen=True, slots=True)
class ExtractionJobId:
    """The unique identifier for extraction jobs.

    The identifier consists of a single instance component (UUIDv7).

    Attributes:
        instance: A unique id for the runtime instance (UUIDv7).
    """

    instance: InstanceId

    def __str__(self) -> str:
        """User-friendly string representation of the extraction job ID."""
        return str(self.instance)

    def __repr__(self) -> str:
        """Developer-friendly string representation of the extraction job ID."""
        return f'ExtractionJobId(instance={self.instance})'

    @classmethod
    def generate_new(cls) -> Self:
        """Create a new ExtractionJobId with a generated instance component.

        Returns:
            A new ExtractionJobId with a unique instance component.
        """
        return cls(instance=InstanceId.generate())

    @classmethod
    def from_instance(cls, instance: InstanceId) -> Self:
        """Create an ExtractionJobId from an already existing instance component.

        Args:
            instance: The unique id for the runtime instance.

        Returns:
            An ExtractionJobId with the provided instance component.
        """
        return cls(instance=instance)


@dataclass(frozen=True, slots=True)
class ExtractionBatchId:
    """The unique identifier for extraction batches.

    The identifier consists of a single instance component (UUIDv7).

    Attributes:
        instance: A unique id for the runtime instance (UUIDv7).
    """

    instance: InstanceId

    def __str__(self) -> str:
        """User-friendly string representation of the extraction batch ID."""
        return str(self.instance)

    def __repr__(self) -> str:
        """Developer-friendly string representation of the extraction batch ID."""
        return f'ExtractionBatchId(instance={self.instance})'

    @classmethod
    def generate_new(cls) -> Self:
        """Create a new ExtractionBatchId with a generated instance component.

        Returns:
            A new ExtractionBatchId with a unique instance component.
        """
        return cls(instance=InstanceId.generate())

    @classmethod
    def from_instance(cls, instance: InstanceId) -> Self:
        """Create an ExtractionBatchId from an already existing instance component.

        Args:
            instance: The unique id for the runtime instance.

        Returns:
            An ExtractionBatchId with the provided instance component.
        """
        return cls(instance=instance)
