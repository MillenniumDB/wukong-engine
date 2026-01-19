from typing import Literal

# Fields
# TODO: Add all data types
# FieldTypeToken = Literal['string', 'str', 'integer', 'int', 'float', 'double', 'boolean', 'bool']
FieldTypeToken = Literal['string', 'str']
FieldModeToken = Literal['extract', 'llm', 'load', 'external', 'default', 'placeholder', 'skip', 'ignore', 'omit']
ContentLevelToken = Literal['chunk', 'document']
