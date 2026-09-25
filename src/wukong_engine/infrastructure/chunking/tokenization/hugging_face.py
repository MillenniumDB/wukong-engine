"""Text tokenizer backed by Hugging Face transformers."""

# Disable advisory warnings
import os

os.environ['TRANSFORMERS_NO_ADVISORY_WARNINGS'] = '1'

from transformers import AutoTokenizer, PreTrainedTokenizerFast

from .text_tokenizer import TextTokenizer
from .tokenized_text import TokenizedText

# Universal-like tokenizer model
DEFAULT_TOKENIZER_MODEL_NAME = 'Qwen/Qwen2.5-7B'


class HuggingFaceTokenizer(TextTokenizer):
    """Tokenizer backed by Hugging Face transformers."""

    def __init__(self, model_name: str = DEFAULT_TOKENIZER_MODEL_NAME) -> None:
        """Initialize with a specific Hugging Face tokenizer model.

        Args:
            model_name: Hugging Face model identifier whose tokenizer is loaded.

        Raises:
            TypeError: If the loaded tokenizer is not a fast tokenizer.
        """
        self._tokenizer = self._load(model_name)

    @staticmethod
    def _load(model_name: str) -> PreTrainedTokenizerFast:
        """Load the fast tokenizer for a Hugging Face model.

        Args:
            model_name: Hugging Face model identifier whose tokenizer is loaded.

        Returns:
            The loaded fast tokenizer.

        Raises:
            TypeError: If the loaded tokenizer is not a fast tokenizer.
        """
        tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=True)
        if not isinstance(tokenizer, PreTrainedTokenizerFast):
            raise TypeError(f"Tokenizer '{model_name}' is not a fast tokenizer.")
        return tokenizer

    def tokenize(self, text: str) -> TokenizedText:
        """Tokenize a given text.

        Args:
            text: Text to tokenize.

        Returns:
            The text with the character offsets of its tokens, excluding special tokens and tokens with empty
            offsets.
        """
        encoding = self._tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)

        # Gather all valid offsets
        starts: list[int] = []
        ends: list[int] = []
        for start, end in encoding['offset_mapping']:
            if start != end:
                starts.append(start)
                ends.append(end)
        return TokenizedText(text=text, token_starts=tuple(starts), token_ends=tuple(ends))

    def truncate(self, text: str, max_tokens: int) -> str:
        """Truncate a given text to fit within the max token limit.

        Args:
            text: Text to truncate.
            max_tokens: Maximum number of tokens, excluding special tokens, to keep.

        Returns:
            The text decoded from its first ``max_tokens`` tokens.

        Raises:
            ValueError: If the decoded text is not a string.
        """
        encoded = self._tokenizer(text, add_special_tokens=False, truncation=True, max_length=max_tokens)
        decoded = self._tokenizer.decode(encoded['input_ids'], skip_special_tokens=True)
        if isinstance(decoded, str):
            return decoded
        raise ValueError('Decoded truncated text is not a string.')
