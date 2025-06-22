# Data Model Format

This tool expects a data model file in JSON format. The file must follow a specific structure:

## Required Fields

- `name`: string
- `fields`: list of objects with `id`, `type`, and `label`

## Example

```json
{
  "name": "Person",
  "fields": [
    {"id": "first_name", "type": "string", "label": "First Name"},
    {"id": "age", "type": "integer", "label": "Age"}
  ]
}
```

## Conventions

- Field `id`s should be unique
- Supported types: string, integer, boolean, date
