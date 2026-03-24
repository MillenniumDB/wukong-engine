from dataclasses import dataclass

from .llm import LLMConfig
from .pipeline import PipelineConfig


@dataclass(frozen=True)
class ApplicationConfig:
    """Top-level application configuration."""

    pipeline: PipelineConfig
    llm: LLMConfig

    def __str__(self) -> str:
        """User-friendly string representation of the application configuration."""
        lines = []
        lines.append('=' * 80)
        lines.append(' CONFIGURATION')
        lines.append('=' * 80)

        # Pipeline Config
        lines.append('\n[PIPELINE]\n')
        lines.extend(f'  {line}' for line in str(self.pipeline).split('\n'))

        # LLM Config
        lines.append('\n[LLM]\n')
        lines.extend(f'  {line}' for line in str(self.llm).split('\n'))

        lines.append('\n' + '=' * 80 + '\n')
        return '\n'.join(lines)
