"""Document source normalization utilities."""

from wukong_engine.core.documents.model.source import DocumentSource
from wukong_engine.core.documents.model.values import DocumentSourceMode


class DocumentSourceNormalizer:
    """Normalize document sources by removing redundant entries."""

    def normalize(self, sources: tuple[DocumentSource, ...]) -> tuple[DocumentSource, ...]:
        """Return a tuple of sources with redundant entries removed."""
        to_remove: set[DocumentSource] = set()
        source_list = list(sources)

        for idx_a, source_a in enumerate(source_list):
            for idx_b, source_b in enumerate(source_list):
                if idx_a >= idx_b or source_a in to_remove or source_b in to_remove:
                    continue
                redundant = self._detect_redundant_source(source_a, source_b)
                if redundant is not None:
                    to_remove.add(redundant)

        if not to_remove:
            return sources
        return tuple(source for source in sources if source not in to_remove)

    @staticmethod
    def _detect_redundant_source(a: DocumentSource, b: DocumentSource) -> DocumentSource | None:
        """Return whichever of a/b is made redundant by the other, or None."""
        detectors = {
            frozenset({DocumentSourceMode.FILE}): DocumentSourceNormalizer._detect_equal_source,
            frozenset({DocumentSourceMode.DIRECTORY}): DocumentSourceNormalizer._detect_equal_source,
            frozenset({DocumentSourceMode.RECURSIVE}): DocumentSourceNormalizer._detect_contained_source,
            frozenset(
                {DocumentSourceMode.FILE, DocumentSourceMode.DIRECTORY},
            ): DocumentSourceNormalizer._detect_child_source,
            frozenset(
                {DocumentSourceMode.FILE, DocumentSourceMode.RECURSIVE},
            ): DocumentSourceNormalizer._detect_contained_source,
            frozenset(
                {DocumentSourceMode.DIRECTORY, DocumentSourceMode.RECURSIVE},
            ): DocumentSourceNormalizer._detect_contained_source,
        }
        detector = detectors.get(frozenset({a.mode, b.mode}))
        if detector is None:
            return None
        return detector(a, b)

    @staticmethod
    def _detect_equal_source(a: DocumentSource, b: DocumentSource) -> DocumentSource | None:
        """Return a redundant source when both entries have the same mode and path."""
        if a.mode == b.mode and a.source_path == b.source_path:
            return b
        return None

    @staticmethod
    def _detect_child_source(a: DocumentSource, b: DocumentSource) -> DocumentSource | None:
        """Return a redundant source when contained by the parent directory source."""
        if {a.mode, b.mode} != {DocumentSourceMode.FILE, DocumentSourceMode.DIRECTORY}:
            return None

        dir_src = a if a.mode == DocumentSourceMode.DIRECTORY else b
        file_src = b if dir_src is a else a
        if file_src.source_path.parent == dir_src.source_path:
            return file_src
        return None

    @staticmethod
    def _detect_contained_source(a: DocumentSource, b: DocumentSource) -> DocumentSource | None:
        """Return a redundant source when fully contained by a recursive source."""
        if DocumentSourceMode.RECURSIVE not in {a.mode, b.mode}:
            return None

        if a.mode == b.mode == DocumentSourceMode.RECURSIVE:
            recursive_src = min((a, b), key=lambda source: len(source.source_path.parts))
        else:
            recursive_src = a if a.mode == DocumentSourceMode.RECURSIVE else b

        other_src = b if recursive_src is a else a
        container_paths = set(other_src.source_path.parents)
        if other_src.mode != DocumentSourceMode.FILE:
            container_paths.add(other_src.source_path)
        if recursive_src.source_path in container_paths:
            return other_src
        return None
