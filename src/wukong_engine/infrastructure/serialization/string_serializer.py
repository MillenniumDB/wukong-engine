"""Provides StringSerializer implementations."""

from typing import ClassVar, Protocol


class StringSerializer(Protocol):
    """Serializes and deserializes string values for storage/transmission and retrieval."""

    def serialize(self, value: str) -> str:
        """Serialize a string value.

        Args:
            value: String to serialize.

        Returns:
            The serialized string.
        """
        ...

    def deserialize(self, value: str) -> str:
        """Deserialize a string value.

        Args:
            value: Previously serialized string.

        Returns:
            The original string.
        """
        ...


class IdentityStringSerializer(StringSerializer):
    """Maintains the original string value without any transformation."""

    def serialize(self, value: str) -> str:
        """Serialize a string value.

        Args:
            value: String to serialize.

        Returns:
            The same string, unchanged.
        """
        return value

    def deserialize(self, value: str) -> str:
        """Deserialize a string value.

        Args:
            value: Previously serialized string.

        Returns:
            The same string, unchanged.
        """
        return value


class EscapedStringSerializer(StringSerializer):
    """Escapes control characters while maintaining readability.

    This transformation is reversible, allowing for accurate retrieval of the original string value.

    Rules:
    - Preserves printable characters as-is.
    - Escapes backslashes to avoid ambiguity.
    - Escapes common control characters (e.g., newline, tab) using backslash notation.
    - Escapes other control characters (ASCII 0-31 and 127, excluding the common ones) using hex encoding.
    - Unknown escape sequences are preserved literally as printable characters.
    """

    _ESCAPE_MAP: ClassVar[dict[str, str]] = {
        '\\': '\\\\',
        '\n': '\\n',
        '\r': '\\r',
        '\t': '\\t',
        '\b': '\\b',
        '\f': '\\f',
        '\v': '\\v',
        '\0': '\\0',
    }

    _SIMPLE_ESCAPES: ClassVar[dict[str, str]] = {
        'n': '\n',
        'r': '\r',
        't': '\t',
        'b': '\b',
        'f': '\f',
        'v': '\v',
        '\\': '\\',
        '0': '\0',
    }

    def serialize(self, value: str) -> str:
        """Serialize a string value.

        Args:
            value: String to escape.

        Returns:
            The string with backslashes and control characters escaped.
        """
        out = []

        # Loop through the string and escape control characters
        for char in value:
            # Escape common control characters using the escape map
            if char in self._ESCAPE_MAP:
                out.append(self._ESCAPE_MAP[char])

            # Escape rare control characters using hex encoding
            elif ord(char) < 32 or ord(char) == 127:  # noqa: PLR2004
                out.append(f'\\x{ord(char):02X}')

            # Keep printable characters as-is
            else:
                out.append(char)

        return ''.join(out)

    def deserialize(self, value: str) -> str:
        """Deserialize a string value.

        Args:
            value: Escaped string produced by ``serialize``.

        Returns:
            The string with escape sequences decoded; unknown or malformed escapes are kept literally.
        """
        out = []
        i = 0

        # Loop through the string and deserialize escaped sequences
        while i < len(value):
            ch = value[i]

            # Non-escaped sequences are added directly to the output
            if ch != '\\':
                out.append(ch)
                i += 1
                continue

            # Edge Case: Final character is a backslash
            if i + 1 >= len(value):
                out.append('\\')
                break

            # Handle simple escaped sequences
            nxt = value[i + 1]
            if nxt in self._SIMPLE_ESCAPES:
                out.append(self._SIMPLE_ESCAPES[nxt])
                i += 2
                continue

            # Handle hex-encoded sequences
            if nxt == 'x' and i + 3 < len(value):
                try:
                    out.append(chr(int(value[i + 2 : i + 4], 16)))
                    i += 4
                    continue
                except ValueError:
                    pass

            # Unknown escape -> preserve literally
            out.append('\\')
            i += 1

        return ''.join(out)
