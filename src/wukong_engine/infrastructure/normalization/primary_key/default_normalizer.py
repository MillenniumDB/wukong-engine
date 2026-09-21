"""Provides the DefaultPKNormalizer class."""

import re
import unicodedata

from unidecode import unidecode

from wukong_engine.app.data_extraction.ports import PKNormalizer
from wukong_engine.core.knowledge.elements.values import NormalizedPK


class DefaultPKNormalizer(PKNormalizer):
    """Normalizes raw primary key values into a consistent format using standard string manipulation and unicode transliteration."""

    def normalize(self, raw_pk: str) -> NormalizedPK | None:
        """Normalize a raw primary key value."""
        # Unicode normalization
        value = unicodedata.normalize('NFKC', raw_pk)

        # Remove non-printable chars
        value = ''.join(c for c in value if c.isprintable())

        # Normalize dashes
        value = value.replace('–', '-').replace('—', '-')  # noqa: RUF001

        # Case normalization
        value = value.casefold()

        # Unicode transliteration
        value = unidecode(value)

        # Remove disallowed characters
        value = re.sub(rf'[^{NormalizedPK.ALLOWED_CHARS_PATTERN}]', '', value)

        # Trim forbidden edge characters
        value = re.sub(
            rf'^[{NormalizedPK.FORBIDDEN_EDGE_CHARS_PATTERN}]+|[{NormalizedPK.FORBIDDEN_EDGE_CHARS_PATTERN}]+$',
            '',
            value,
        )

        # Normalize whitespace
        value = re.sub(r'\s+', ' ', value)

        # Final validation and return
        try:
            return NormalizedPK(value)
        except ValueError:  # Invalid raw PK -> Invalid normalized PK
            return None
