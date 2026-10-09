"""Scopes and reasons of the rejections made while validating extraction results."""

from enum import Enum


class RejectionScope(Enum):
    """What a rejection removes from an extraction result.

    Attributes:
        OBJECT: The whole entity or relationship is discarded.
        VALUE: A single optional value is unset, and its entity or relationship is kept.
    """

    OBJECT = 'OBJECT'
    VALUE = 'VALUE'


class RejectionReason(Enum):
    """Why an extracted entity or relationship, or one of its values, was rejected.

    Attributes:
        UNKNOWN_TYPE: The type is missing, unknown to the knowledge model, or not assigned to the job.
        MISSING_VALUE: A required field, or the primary key, has no value.
        INVALID_OPTION: A value is outside the field's allowed options.
        REGEX_MISMATCH: A value doesn't match the field's regex.
        INVALID_PRIMARY_KEY: The primary key value doesn't normalize (e.g. it is empty once normalized).
        MISSING_ENDPOINT: The source or target ID is missing.
        UNRESOLVED_ENDPOINT: The source or target ID doesn't refer to an entity shown to the LLM.
        INVALID_ENDPOINT: The source and target don't match any endpoint of the relationship type.
        SELF_LOOP: The source and target are the same entity, on an irreflexive relationship type.
        EXTRA_DOCUMENT_ENTITY: A document-level job returned a second, different entity of a type it already returned
            one of. A document-level type stands for the document itself, so only the first valid one is kept.
    """

    UNKNOWN_TYPE = 'UNKNOWN_TYPE'
    MISSING_VALUE = 'MISSING_VALUE'
    INVALID_OPTION = 'INVALID_OPTION'
    REGEX_MISMATCH = 'REGEX_MISMATCH'
    INVALID_PRIMARY_KEY = 'INVALID_PRIMARY_KEY'
    MISSING_ENDPOINT = 'MISSING_ENDPOINT'
    UNRESOLVED_ENDPOINT = 'UNRESOLVED_ENDPOINT'
    INVALID_ENDPOINT = 'INVALID_ENDPOINT'
    SELF_LOOP = 'SELF_LOOP'
    EXTRA_DOCUMENT_ENTITY = 'EXTRA_DOCUMENT_ENTITY'
