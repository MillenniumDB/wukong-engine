"""Top-level application configuration."""

from dataclasses import dataclass

from .chunking import ChunkingConfig
from .export import ExportConfig
from .llm import LLMConfig
from .pipeline import PipelineConfig


@dataclass(frozen=True, slots=True)
class ApplicationConfig:
    """Top-level application configuration.

    Attributes:
        pipeline: Which pipeline steps are enabled.
        llm: LLM model, execution mode and concurrency settings.
        chunking: Document chunking token budgets.
        export: Knowledge export settings.
    """

    pipeline: PipelineConfig
    llm: LLMConfig
    chunking: ChunkingConfig
    export: ExportConfig

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

        # Chunking Config
        lines.append('\n[CHUNKING]\n')
        lines.extend(f'  {line}' for line in str(self.chunking).split('\n'))

        # Export Config
        lines.append('\n[EXPORT]\n')
        lines.extend(f'  {line}' for line in str(self.export).split('\n)'))

        lines.append('\n' + '=' * 80 + '\n')
        return '\n'.join(lines)
