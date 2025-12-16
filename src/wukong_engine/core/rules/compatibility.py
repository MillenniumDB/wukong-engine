from wukong_engine.core.enums import FieldMode, Source

# Source to allowed FieldModes mapping
SOURCE_MODES: dict[Source, set[FieldMode]] = {
    Source.CHUNK: {FieldMode.EXTRACTION, FieldMode.DEFAULT, FieldMode.SKIP},
    Source.DOCUMENT: {FieldMode.EXTRACTION, FieldMode.EXTERNAL, FieldMode.DEFAULT, FieldMode.SKIP},
}
