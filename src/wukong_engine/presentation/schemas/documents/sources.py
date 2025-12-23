import re
from typing import Any

from pydantic import BaseModel, Field, StrictBool, StrictStr, field_validator


class DocumentSourceSchema(BaseModel):
    """Schema-level representation of a field definition."""

    name: StrictStr
    # TODO:
