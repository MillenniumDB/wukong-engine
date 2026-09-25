"""Document source normalization utilities."""

from pathlib import Path

from wukong_engine.core.documents.model.source import DocumentSource
from wukong_engine.core.documents.model.values import DocumentSourceMode


class DocumentSourceNormalizer:
    """Normalize document sources by removing redundant entries."""

    def normalize(self, sources: tuple[DocumentSource, ...]) -> tuple[DocumentSource, ...]:
        """Return a tuple of sources with redundant entries removed.

        A source is redundant when another source already covers all of its documents (a duplicate, a file inside a
        directory source, or a path inside a recursive source).

        Args:
            sources: Document sources to normalize.

        Returns:
            The remaining sources in their original order, or ``sources`` itself if nothing was redundant.
        """
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
        """Return whichever of a/b is made redundant by the other, or None.

        Args:
            a: First source to compare.
            b: Second source to compare.

        Returns:
            The redundant source, or None if neither source covers the other.
        """
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
        """Return a redundant source when both entries have the same mode and path.

        Args:
            a: First source to compare.
            b: Second source to compare.

        Returns:
            ``b`` if both sources are equal, None otherwise.
        """
        if a == b:
            return b
        return None

    @staticmethod
    def _detect_child_source(a: DocumentSource, b: DocumentSource) -> DocumentSource | None:
        """Return a redundant source when contained by the parent directory source.

        Args:
            a: First source to compare; one of a/b must be a FILE source and the other a DIRECTORY source.
            b: Second source to compare.

        Returns:
            The FILE source if it sits directly in the DIRECTORY source's root, None otherwise.
        """
        if {a.mode, b.mode} != {DocumentSourceMode.FILE, DocumentSourceMode.DIRECTORY}:
            return None

        dir_src = a if a.mode == DocumentSourceMode.DIRECTORY else b
        file_src = b if dir_src is a else a
        if Path(file_src.root).parent == Path(dir_src.root):
            return file_src
        return None

    @staticmethod
    def _detect_contained_source(a: DocumentSource, b: DocumentSource) -> DocumentSource | None:
        """Return a redundant source when fully contained by a recursive source.

        When both sources are RECURSIVE, the one with the shallower root is treated as the container.

        Args:
            a: First source to compare; at least one of a/b must be a RECURSIVE source.
            b: Second source to compare.

        Returns:
            The other source if its root is at or below the recursive source's root, None otherwise.
        """
        if DocumentSourceMode.RECURSIVE not in {a.mode, b.mode}:
            return None

        if a.mode == b.mode == DocumentSourceMode.RECURSIVE:
            recursive_src = min((a, b), key=lambda source: len(Path(source.root).parts))
        else:
            recursive_src = a if a.mode == DocumentSourceMode.RECURSIVE else b

        other_src = b if recursive_src is a else a
        container_paths = set(Path(other_src.root).parents)
        if other_src.mode != DocumentSourceMode.FILE:
            container_paths.add(Path(other_src.root))
        if Path(recursive_src.root) in container_paths:
            return other_src
        return None
