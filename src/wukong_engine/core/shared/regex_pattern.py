"""Validated regular expression pattern."""

import re


class RegexPattern:
    """A validated regex pattern.

    Attributes:
        pattern: Source string of the regex pattern.
    """

    def __init__(self, pattern: str) -> None:
        """Initialize and validate the regex pattern.

        Args:
            pattern: The regex pattern string.

        Raises:
            ValueError: If the pattern is not a valid regex.
        """
        try:
            compiled = re.compile(pattern)
        except re.error as error:
            raise ValueError(f'Invalid regex pattern "{pattern}": {error}') from error

        self.pattern = pattern
        self._compiled = compiled

    def fullmatch(self, text: str) -> re.Match[str] | None:
        """Match the regex pattern against the whole text.

        Args:
            text: The text to match against.

        Returns:
            A match object if the pattern matches all of ``text``, None otherwise (including when it only matches a
            prefix of it).
        """
        return self._compiled.fullmatch(text)
