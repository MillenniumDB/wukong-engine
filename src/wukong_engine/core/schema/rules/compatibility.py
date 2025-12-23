from wukong_engine.core.enums import ContentLevel, FieldMode

# Content Level to allowed Field Modes mapping
CONTENT_MODES: dict[ContentLevel, set[FieldMode]] = {
    ContentLevel.CHUNK: {FieldMode.EXTRACTION, FieldMode.DEFAULT, FieldMode.SKIP},
    ContentLevel.DOCUMENT: {FieldMode.EXTRACTION, FieldMode.EXTERNAL, FieldMode.DEFAULT, FieldMode.SKIP},
}
