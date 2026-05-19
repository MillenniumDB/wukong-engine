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
        """Initialize with a specific Hugging Face tokenizer model."""
        self._tokenizer = self._load(model_name)

    @staticmethod
    def _load(model_name: str) -> PreTrainedTokenizerFast:
        tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=True)
        if not isinstance(tokenizer, PreTrainedTokenizerFast):
            raise TypeError(f"Tokenizer '{model_name}' is not a fast tokenizer.")
        return tokenizer

    def tokenize(self, text: str) -> TokenizedText:
        """Tokenize a given text."""
        encoding = self._tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)

        # Gather all valid offsets
        starts: list[int] = []
        ends: list[int] = []
        for start, end in encoding['offset_mapping']:
            if start != end:
                starts.append(start)
                ends.append(end)
        return TokenizedText(text=text, token_starts=tuple(starts), token_ends=tuple(ends))
