"""Provides a data model interface for the engine.

This module defines the `DataModel` class, responsible for loading,
validating, and providing access to the user-defined data model required by the engine.

Classes:
    DataModel: A singleton class that manages the data model for the engine.

Example:
    from wukong_engine.core.data_model import DataModel

    data_model = DataModel()
    entities = data_model.entities
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
