"""Instance and content-based identifiers shared across the engine."""

import hashlib
import uuid
from dataclasses import dataclass
from typing import ClassVar, Self


@dataclass(frozen=True, slots=True)
class InstanceId:
    """A global unique identifier for a runtime instance, using UUIDv7.

    The identifier is stored as the 16 raw bytes of the UUID.
    """

    _value: bytes

    # Parameters for UUID
    _UUID_SIZE: ClassVar[int] = 16  # 16 bytes → 128 bits → 32 hex chars

    @classmethod
    def generate(cls) -> Self:
        """Generate a new InstanceId.

        Returns:
            A new identifier backed by a freshly generated UUIDv7.
        """
        return cls(uuid.uuid7().bytes[: cls._UUID_SIZE])

    @classmethod
    def from_bytes(cls, data: bytes) -> Self:
        """Import an existing InstanceId from raw bytes.

        Args:
            data: Raw 16-byte UUID.

        Returns:
            The identifier wrapping the given bytes.

        Raises:
            ValueError: If ``data`` isn't 16 bytes long.
        """
        return cls(data)

    @classmethod
    def from_hex(cls, hex_str: str) -> Self:
        """Import an existing InstanceId from a hexadecimal string.

        Args:
            hex_str: 32-character hexadecimal representation of the UUID.

        Returns:
            The identifier for the decoded bytes.

        Raises:
            ValueError: If ``hex_str`` isn't valid hexadecimal or doesn't decode to 16 bytes.
        """
        return cls(bytes.fromhex(hex_str))

    def __post_init__(self) -> None:
        """Validate instance id invariants.

        Raises:
            ValueError: If the UUID isn't 16 bytes long.
        """
        self._validate_uuid()

    def _validate_uuid(self) -> None:
        """Validate that the UUID has the correct length.

        Raises:
            ValueError: If the UUID isn't 16 bytes long.
        """
        if len(self._value) != self._UUID_SIZE:
            raise ValueError(
                f'Invalid UUID length: expected {self._UUID_SIZE} bytes, got {len(self._value)}',
            )

    @property
    def bytes(self) -> bytes:
        """Raw bytes representation of the instance ID."""
        return self._value

    @property
    def hex(self) -> str:
        """Hexadecimal string representation of the instance ID."""
        return self._value.hex()

    def __str__(self) -> str:
        """User-friendly string representation of the instance ID."""
        return self.hex


@dataclass(frozen=True, slots=True)
class ContentHash:
    """A content-based hash for efficient representation.

    The hash is the first 16 bytes of the SHA-256 digest of the content.
    """

    _value: bytes

    # Parameters for hashing
    _HASH_SIZE: ClassVar[int] = 16  # 16 bytes → 128 bits → 32 hex chars

    @classmethod
    def from_content_bytes(cls, content: bytes) -> Self:
        """Generate a ContentHash from bytes data.

        Args:
            content: Content to hash.

        Returns:
            The hash of the content.
        """
        return cls(hashlib.sha256(content).digest()[: cls._HASH_SIZE])

    @classmethod
    def from_content_string(cls, content: str, encoding: str = 'utf-8') -> Self:
        """Generate a ContentHash from string data.

        Args:
            content: Content to hash.
            encoding: Encoding used to convert the content to bytes before hashing.

        Returns:
            The hash of the encoded content.
        """
        return cls(hashlib.sha256(content.encode(encoding=encoding)).digest()[: cls._HASH_SIZE])

    @classmethod
    def from_bytes(cls, data: bytes) -> Self:
        """Import an existing ContentHash from raw bytes.

        Args:
            data: Raw 16-byte hash.

        Returns:
            The hash wrapping the given bytes.

        Raises:
            ValueError: If ``data`` isn't 16 bytes long.
        """
        return cls(data)

    @classmethod
    def from_hex(cls, hex_str: str) -> Self:
        """Import an existing ContentHash from a hexadecimal string.

        Args:
            hex_str: 32-character hexadecimal representation of the hash.

        Returns:
            The hash for the decoded bytes.

        Raises:
            ValueError: If ``hex_str`` isn't valid hexadecimal or doesn't decode to 16 bytes.
        """
        return cls(bytes.fromhex(hex_str))

    def __post_init__(self) -> None:
        """Validate content hash invariants.

        Raises:
            ValueError: If the hash isn't 16 bytes long.
        """
        self._validate_hash()

    def _validate_hash(self) -> None:
        """Validate that the hash has the correct length.

        Raises:
            ValueError: If the hash isn't 16 bytes long.
        """
        if len(self._value) != self._HASH_SIZE:
            raise ValueError(
                f'Invalid hash length: expected {self._HASH_SIZE} bytes, got {len(self._value)}',
            )

    @property
    def bytes(self) -> bytes:
        """Raw bytes representation of the content hash."""
        return self._value

    @property
    def hex(self) -> str:
        """Hexadecimal string representation of the content hash."""
        return self._value.hex()

    def __str__(self) -> str:
        """User-friendly string representation of the content hash."""
        return self.hex
