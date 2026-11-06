"""Statistics of what the knowledge construction pipeline produced in a workspace, and what it took."""

from dataclasses import dataclass
from datetime import UTC, datetime

from wukong_engine.app.data_extraction.elements.values import PerformanceMetricsState, TokenUsageMetrics
from wukong_engine.app.data_extraction.model.values import ExecutionMode
from wukong_engine.app.data_extraction.services import ExtractionRepository
from wukong_engine.app.knowledge_export.elements import ExportReport
from wukong_engine.app.llm.model import LLM, LLMRegistry
from wukong_engine.app.shared.formatting import format_count, format_duration, format_size
from wukong_engine.app.staging.ports import UnitOfWork
from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.pipeline.model.values import PipelineStep

from .ports import RunStatsWriter

LINE_WIDTH = 80


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """Tokens used by LLM requests, in categories that don't overlap.

    Attributes:
        input: Input tokens that neither read from nor wrote to the cache.
        cached: Input tokens read from the cache.
        cache_write: Input tokens written to the cache.
        output: Output tokens, excluding reasoning tokens.
        reasoning: Output tokens attributed to reasoning.
    """

    input: int = 0
    cached: int = 0
    cache_write: int = 0
    output: int = 0
    reasoning: int = 0

    @classmethod
    def from_metrics(cls, metrics: TokenUsageMetrics) -> TokenUsage:
        """Build the usage from recorded token metrics, counting missing categories as zero.

        Args:
            metrics: Recorded token usage.

        Returns:
            The token usage.
        """
        return cls(
            input=metrics.input_tokens or 0,
            cached=metrics.cached_tokens or 0,
            cache_write=metrics.cache_write_tokens or 0,
            output=metrics.output_tokens or 0,
            reasoning=metrics.reasoning_tokens or 0,
        )

    @property
    def total(self) -> int:
        """Total number of tokens used."""
        return self.input + self.cached + self.cache_write + self.output + self.reasoning

    def __add__(self, other: TokenUsage) -> TokenUsage:
        """Add up two token usages, category by category."""
        return TokenUsage(
            input=self.input + other.input,
            cached=self.cached + other.cached,
            cache_write=self.cache_write + other.cache_write,
            output=self.output + other.output,
            reasoning=self.reasoning + other.reasoning,
        )


@dataclass(frozen=True, slots=True)
class CollectionStats:
    """Ingested contents of a document collection.

    Attributes:
        documents: Number of documents of the collection.
        chunks: Number of chunks of those documents.
    """

    documents: int
    chunks: int


@dataclass(frozen=True, slots=True)
class DocumentStats:
    """Ingested documents and chunks.

    Attributes:
        documents: Number of unique documents.
        chunks: Number of chunks.
        shared_documents: Number of documents belonging to more than one collection, stored once.
        empty_documents: Number of documents without any chunk.
        collections: Contents of each collection, keyed by collection name.
    """

    documents: int
    chunks: int
    shared_documents: int
    empty_documents: int
    collections: dict[str, CollectionStats]


@dataclass(frozen=True, slots=True)
class ExtractionLevelStats:
    """Progress and results of an extraction step at one context level.

    Attributes:
        context_level: Context level the sources belong to.
        sources: Number of sources to extract.
        completed: Number of sources extracted.
        failed: Number of sources whose extraction failed for good.
        objects: Number of unique objects extracted.
        mentions: Number of mentions of those objects across sources.
        tokens: Tokens used by the extraction requests, failed ones included.
    """

    context_level: str
    sources: int
    completed: int
    failed: int
    objects: int
    mentions: int
    tokens: TokenUsage


@dataclass(frozen=True, slots=True)
class ExtractionStats:
    """Progress, results and cost of an extraction step.

    Attributes:
        levels: Stats at each context level that has sources, in extraction order.
        tokens: Tokens used at every context level.
        estimated_cost_usd: Estimated price of those tokens in US dollars, or None if the model's rates aren't known.
    """

    levels: tuple[ExtractionLevelStats, ...]
    tokens: TokenUsage
    estimated_cost_usd: float | None


@dataclass(frozen=True, slots=True)
class RunStats:
    """What the pipeline produced in a workspace, and what it took.

    Results and token usage cover the workspace as it is, which several runs may have built. Durations are given both
    for this run and for every run of each step since it was last reset.

    Attributes:
        finished_at: When the stats were taken, in ISO 8601 with a UTC offset.
        model: Name of the LLM the run is configured with.
        execution_mode: Execution mode the run is configured with.
        export_format: Name of the export format the run is configured with.
        token_rates_as_of: Date of the token prices the cost is estimated with, or None if the model has none.
        this_run_seconds: Time each step took in this run, in seconds, for the steps that ran.
        all_runs_seconds: Time spent on each step across every run since it was last reset, in seconds.
        documents: Ingested documents and chunks.
        entities: Entity extraction progress, results and cost.
        relationships: Relationship extraction progress, results and cost.
        export: What this run exported, or None if it exported nothing.
    """

    finished_at: str
    model: str
    execution_mode: str
    export_format: str
    token_rates_as_of: str | None
    this_run_seconds: dict[str, float]
    all_runs_seconds: dict[str, float]
    documents: DocumentStats
    entities: ExtractionStats
    relationships: ExtractionStats
    export: ExportReport | None

    @property
    def tokens(self) -> TokenUsage:
        """Tokens used by every extraction step."""
        return self.entities.tokens + self.relationships.tokens

    @property
    def estimated_cost_usd(self) -> float | None:
        """Estimated price of the tokens of every extraction step in US dollars, or None if it isn't known."""
        if self.entities.estimated_cost_usd is None or self.relationships.estimated_cost_usd is None:
            return None
        return self.entities.estimated_cost_usd + self.relationships.estimated_cost_usd

    def step_summary(self, step: PipelineStep) -> str:
        """Summarize what a step has produced so far, in a line.

        Args:
            step: Step to summarize.

        Returns:
            The step's key numbers.
        """
        match step:
            case PipelineStep.INGEST_DOCUMENTS:
                return (
                    f'{format_count(self.documents.documents)} documents, '
                    f'{format_count(self.documents.chunks)} chunks from {len(self.documents.collections)} collections'
                )
            case PipelineStep.EXTRACT_ENTITIES:
                return _extraction_summary(self.entities, 'entities')
            case PipelineStep.EXTRACT_RELATIONSHIPS:
                return _extraction_summary(self.relationships, 'relationships')
            case PipelineStep.EXPORT_KNOWLEDGE:
                if self.export is None:
                    return 'nothing exported'
                return (
                    f'{format_count(sum(self.export.nodes.values()))} nodes, '
                    f'{format_count(sum(self.export.edges.values()))} edges, '
                    f'{format_size(self.export.total_bytes)} in {self.export.directory}'
                )

    def __str__(self) -> str:
        """User-friendly report of the stats."""
        lines = ['=' * LINE_WIDTH, ' RUN STATS', '=' * LINE_WIDTH]
        lines += self._duration_lines()
        lines += self._document_lines()
        lines += self._extraction_lines()
        lines += self._token_lines()
        lines += self._output_lines()
        lines.append('\n' + '=' * LINE_WIDTH)
        return '\n'.join(lines)

    def _duration_lines(self) -> list[str]:
        """Lines of the duration section."""
        lines = ['\n[DURATION]\n', f'  {"":<24}{"This run":>12}{"All runs":>12}']
        for step in PipelineStep:
            this_run_seconds = self.this_run_seconds.get(step.value)
            all_runs_seconds = self.all_runs_seconds.get(step.value)
            lines.append(
                f'  {step.value:<24}'
                f'{format_duration(this_run_seconds) if this_run_seconds is not None else "-":>12}'
                f'{format_duration(all_runs_seconds) if all_runs_seconds is not None else "-":>12}',
            )
        lines.append(
            f'  {"Total":<24}{format_duration(sum(self.this_run_seconds.values())):>12}'
            f'{format_duration(sum(self.all_runs_seconds.values())):>12}',
        )
        return lines

    def _document_lines(self) -> list[str]:
        """Lines of the documents section."""
        documents = self.documents
        lines = [
            '\n[DOCUMENTS]\n',
            f'  {"Documents:":<24}{format_count(documents.documents):>12}',
            f'  {"Chunks:":<24}{format_count(documents.chunks):>12}',
            f'  {"In several collections:":<24}{format_count(documents.shared_documents):>12}',
            f'  {"Empty (no chunks):":<24}{format_count(documents.empty_documents):>12}',
        ]
        if documents.collections:
            lines.append(f'\n  {"Collection":<24}{"Documents":>12}{"Chunks":>12}')
            lines += [
                f'  {name:<24}{format_count(collection.documents):>12}{format_count(collection.chunks):>12}'
                for name, collection in documents.collections.items()
            ]
        return lines

    def _extraction_lines(self) -> list[str]:
        """Lines of the extraction section."""
        lines = [
            '\n[EXTRACTION]\n',
            f'  {"":<24}{"Sources":>12}{"Extracted":>12}{"Failed":>10}{"Objects":>10}{"Mentions":>10}',
        ]
        for name, stats in (('Entities', self.entities), ('Relationships', self.relationships)):
            if not stats.levels:
                lines.append(f'  {name:<24}{"-":>12}')
            lines.extend(
                f'  {f"{name} ({level.context_level}S)":<24}'
                f'{format_count(level.sources):>12}{format_count(level.completed):>12}'
                f'{format_count(level.failed):>10}{format_count(level.objects):>10}{format_count(level.mentions):>10}'
                for level in stats.levels
            )
        return lines

    def _token_lines(self) -> list[str]:
        """Lines of the token usage and cost section."""
        header = (
            f'  {"":<16}{"Input":>10}{"Cached":>10}{"Cache wr.":>10}{"Output":>10}{"Reasoning":>10}{"Total":>10}'
            f'{"Est. cost":>11}'
        )
        lines = [f'\n[TOKENS] ({self.model}, {self.execution_mode.lower()})\n', header]
        for name, tokens, cost in (
            ('Entities', self.entities.tokens, self.entities.estimated_cost_usd),
            ('Relationships', self.relationships.tokens, self.relationships.estimated_cost_usd),
            ('Total', self.tokens, self.estimated_cost_usd),
        ):
            counts = (tokens.input, tokens.cached, tokens.cache_write, tokens.output, tokens.reasoning, tokens.total)
            lines.append(
                f'  {name:<16}'
                + ''.join(f'{format_count(count):>10}' for count in counts)
                + f'{_format_cost(cost):>11}',
            )
        if self.token_rates_as_of is None:
            lines.append(f'\n  No token rates are known for {self.model}, so no cost is estimated.')
        else:
            lines.append(
                f'\n  Costs are estimated with the prices {self.model} had on {self.token_rates_as_of}, which may '
                f'have changed since; your provider bill is the reference.',
            )
        return lines

    def _output_lines(self) -> list[str]:
        """Lines of the output section."""
        export = self.export
        if export is None:
            return ['\n[OUTPUT]\n', '  Nothing was exported in this run.']
        files = f'{len(export.files)} {"file" if len(export.files) == 1 else "files"}'
        lines = [
            f'\n[OUTPUT] ({self.export_format})\n',
            f'  {"Directory:":<24}{export.directory}',
            f'  {"Size:":<24}{format_size(export.total_bytes)} in {files}',
            f'\n  {"Nodes":<24}{"Count":>12}',
        ]
        lines += [f'  {label:<24}{format_count(count):>12}' for label, count in export.nodes.items()]
        lines.append(f'  {"Total":<24}{format_count(sum(export.nodes.values())):>12}')
        lines.append(f'\n  {"Edges":<24}{"Count":>12}')
        lines += [f'  {edge_type:<24}{format_count(count):>12}' for edge_type, count in export.edges.items()]
        lines.append(f'  {"Total":<24}{format_count(sum(export.edges.values())):>12}')
        lines.append(
            f'\n  {"Relationship provenance:":<24}{format_count(export.relationship_provenance):>12} chunk references'
        )
        return lines


def _format_cost(cost: float | None) -> str:
    """Format an estimated cost, with cents from a dollar up and more precision below it, or a dash if it isn't known."""
    if cost is None:
        return '-'
    return f'${cost:,.2f}' if cost >= 1 else f'${cost:.4f}'


def _extraction_summary(stats: ExtractionStats, objects: str) -> str:
    """Summarize an extraction step in a line.

    Args:
        stats: Stats of the step.
        objects: Name of the objects the step extracts.

    Returns:
        The sources extracted at each context level, the objects, and the tokens used with their estimated cost.
    """
    if not stats.levels:
        return 'nothing to extract'
    levels = ', '.join(
        f'{level.context_level}S {format_count(level.completed)}/{format_count(level.sources)}'
        + (f' ({format_count(level.failed)} failed)' if level.failed else '')
        for level in stats.levels
    )
    cost = '' if stats.estimated_cost_usd is None else f' (~{_format_cost(stats.estimated_cost_usd)})'
    return (
        f'{levels} sources, {format_count(sum(level.objects for level in stats.levels))} {objects}, '
        f'{format_count(stats.tokens.total)} tokens{cost}'
    )


class RunStatsService:
    """Read the statistics of what the pipeline produced in a workspace and what it took, and record them."""

    def __init__(
        self,
        uow: UnitOfWork,
        entity_repository: ExtractionRepository,
        relationship_repository: ExtractionRepository,
        model: LLM,
        execution_mode: ExecutionMode,
        export_format: str,
        writer: RunStatsWriter,
    ) -> None:
        """Initialize the service with the stores of the workspace and the configuration of the run.

        Args:
            uow: Unit of work used to read ingestion counts and step durations.
            entity_repository: Repository of entity extractions.
            relationship_repository: Repository of relationship extractions.
            model: LLM the run is configured with, whose token rates estimate the cost.
            execution_mode: Execution mode the run is configured with.
            export_format: Name of the export format the run is configured with.
            writer: Writer recording the statistics of a run next to its export.
        """
        self._uow = uow
        self._entity_repository = entity_repository
        self._relationship_repository = relationship_repository
        self._model = model
        self._execution_mode = execution_mode
        self._export_format = export_format
        self._writer = writer

    def collect(self, this_run_seconds: dict[PipelineStep, float], export: ExportReport | None = None) -> RunStats:
        """Read the statistics of the workspace.

        Args:
            this_run_seconds: Time each step took in this run, in seconds, for the steps that ran.
            export: What this run exported, if it exported anything.

        Returns:
            The statistics.
        """
        with self._uow as tx:
            all_runs_seconds = tx.pipeline.get_step_durations()
            documents_by_collection = tx.documents.count_documents_by_collection()
            chunks_by_collection = tx.documents.count_chunks_by_collection()
            documents = DocumentStats(
                documents=tx.documents.count_documents(),
                chunks=tx.documents.count_chunks(),
                shared_documents=tx.documents.count_shared_documents(),
                empty_documents=tx.documents.count_empty_documents(),
                collections={
                    name: CollectionStats(documents=count, chunks=chunks_by_collection.get(name, 0))
                    for name, count in sorted(documents_by_collection.items())
                },
            )
        rates = LLMRegistry.token_rates(self._model)
        return RunStats(
            finished_at=datetime.now(UTC).isoformat(timespec='seconds'),
            model=self._model.name,
            execution_mode=self._execution_mode.value,
            export_format=self._export_format,
            token_rates_as_of=rates.as_of if rates is not None else None,
            this_run_seconds={step.value: round(duration, 3) for step, duration in this_run_seconds.items()},
            all_runs_seconds={step.value: all_runs_seconds[step] for step in PipelineStep if step in all_runs_seconds},
            documents=documents,
            entities=self._extraction_stats(self._entity_repository),
            relationships=self._extraction_stats(self._relationship_repository),
            export=export,
        )

    def save(self, stats: RunStats, directory: str) -> None:
        """Record the statistics of a run in the directory of its export.

        Args:
            stats: Statistics of the run.
            directory: Directory holding the files the run exported.
        """
        self._writer.write(stats, directory)

    def _extraction_stats(self, repository: ExtractionRepository) -> ExtractionStats:
        """Read the progress, results and cost of an extraction step.

        Args:
            repository: Repository of the step's extractions.

        Returns:
            The stats of the step at each context level that has sources.
        """
        rates = LLMRegistry.token_rates(self._model)
        levels = []
        cost = 0.0
        for context_level in (ContextLevel.DOCUMENT, ContextLevel.CHUNK):
            metrics = repository.get_extraction_metrics(context_level, PerformanceMetricsState())
            if metrics.total_sources == 0:
                continue
            usage = {
                mode: TokenUsage.from_metrics(tokens)
                for mode, tokens in repository.get_token_usage_by_execution_mode(context_level).items()
            }
            if rates is not None:
                cost += sum(
                    rates.cost(
                        input_tokens=tokens.input,
                        cached_tokens=tokens.cached,
                        cache_write_tokens=tokens.cache_write,
                        output_tokens=tokens.output + tokens.reasoning,
                        batch=mode is ExecutionMode.BATCH,
                    )
                    for mode, tokens in usage.items()
                )
            levels.append(
                ExtractionLevelStats(
                    context_level=context_level.value,
                    sources=metrics.total_sources,
                    completed=metrics.source_counts['completed'],
                    failed=metrics.source_counts['failed'],
                    objects=metrics.object_count,
                    mentions=metrics.object_mentions,
                    tokens=sum(usage.values(), TokenUsage()),
                ),
            )
        return ExtractionStats(
            levels=tuple(levels),
            tokens=sum((level.tokens for level in levels), TokenUsage()),
            estimated_cost_usd=cost if rates is not None else None,
        )
