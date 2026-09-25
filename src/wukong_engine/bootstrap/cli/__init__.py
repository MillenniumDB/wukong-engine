"""The bootstrap CLI package.

This package handles the wiring of components for CLI entry points.
"""

from .application import build_application

__all__ = ['build_application']
