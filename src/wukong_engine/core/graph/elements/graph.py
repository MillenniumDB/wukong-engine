"""Provides a graph model interface for the engine.

This module defines the `GraphModel` class, responsible for loading,
validating, and providing access to the user-defined graph model required by the engine.

Classes:
    GraphModel: A singleton class that manages the graph model for the engine.

Example:
    from wukong_engine.core.graph_model import GraphModel

    graph_model = GraphModel()
    entities = graph_model.entities
"""

import json
import logging
import re
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .entity import Entity


@dataclass
class Graph: ...
