import hashlib
import uuid
from dataclasses import dataclass
from typing import ClassVar, Self


@dataclass(frozen=True, slots=True)
class InstanceId:
    """A global unique identifier for a runtime instance, using UUIDv7."""

    _value: bytes

    # Parameters for UUID
    _UUID_SIZE: ClassVar[int] = 16  # 16 bytes → 128 bits → 32 hex chars

    @classmethod
    def generate(cls) -> Self:
        """Generate a new InstanceId."""
        return cls(uuid.uuid7().bytes[: cls._UUID_SIZE])

    def __post_init__(self) -> None:
        """Validate instance id invariants."""
        self._validate_uuid()

    def _validate_uuid(self) -> None:
        """Validate that the UUID has the correct length."""
        if len(self._value) != self._UUID_SIZE:
            raise ValueError(
                f'Invalid UUID length: expected {self._UUID_SIZE} bytes, got {len(self._value)}',
            )

    def to_bytes(self) -> bytes:
        """Raw bytes representation of the instance ID."""
        return self._value

    def to_hex(self) -> str:
        """Hexadecimal string representation of the instance ID."""
        return self._value.hex()

    def __str__(self) -> str:
        """User-friendly string representation of the instance ID."""
        return self.to_hex()


@dataclass(frozen=True, slots=True)
class ContentHash:
    """A content-based hash for efficient representation."""

    _value: bytes

    # Parameters for hashing
    _HASH_SIZE: ClassVar[int] = 16  # 16 bytes → 128 bits → 32 hex chars

    @classmethod
    def from_bytes(cls, content: bytes) -> Self:
        """Generate a content hash from bytes data."""
        return cls(hashlib.sha256(content).digest()[: cls._HASH_SIZE])

    @classmethod
    def from_string(cls, content: str, encoding: str = 'utf-8') -> Self:
        """Generate a content hash from string data."""
        return cls(hashlib.sha256(content.encode(encoding=encoding)).digest()[: cls._HASH_SIZE])

    def __post_init__(self) -> None:
        """Validate content hash invariants."""
        self._validate_hash()

    def _validate_hash(self) -> None:
        """Validate that the hash has the correct length."""
        if len(self._value) != self._HASH_SIZE:
            raise ValueError(
                f'Invalid hash length: expected {self._HASH_SIZE} bytes, got {len(self._value)}',
            )

    def to_bytes(self) -> bytes:
        """Raw bytes representation of the content hash."""
        return self._value

    def to_hex(self) -> str:
        """Hexadecimal string representation of the content hash."""
        return self._value.hex()

    def __str__(self) -> str:
        """User-friendly string representation of the content hash."""
        return self.to_hex()
