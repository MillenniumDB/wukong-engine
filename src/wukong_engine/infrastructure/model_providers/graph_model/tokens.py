from typing import Literal

# Fields
# TODO: Add all data types
# DataTypeToken = Literal['string', 'str', 'integer', 'int', 'float', 'double', 'boolean', 'bool']
DataTypeToken = Literal['string', 'str']
RetrievalModeToken = Literal['extract', 'llm', 'load', 'external', 'default', 'placeholder', 'skip', 'ignore', 'omit']
ContextLevelToken = Literal['chunk', 'document']
