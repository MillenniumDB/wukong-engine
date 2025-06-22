# Configuration File

The configuration file is a JSON file used to customize tool behavior.

## Options

- `input_path`: Path to the input data model
- `output_path`: Where to save processed output
- `validate_only`: (bool) If true, only validate input

## Example

```json
{
  "input_path": "models/person.json",
  "output_path": "output/person_processed.json",
  "validate_only": false
}
```