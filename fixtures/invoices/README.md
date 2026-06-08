# Invoice extraction fixtures

Place PDF or image files here for automated evaluation. Each file must have a matching
JSON file in `fixtures/expected/` with the same basename.

## Examples

| Invoice file | Expected JSON |
|--------------|---------------|
| `freelancer-007.pdf` | `fixtures/expected/freelancer-007.json` |
| `albanian-retail-14465.pdf` | `fixtures/expected/albanian-retail-14465.json` |

## Run evaluation

```bash
cd backend
python ../scripts/eval_extraction.py
```

Requires `OPENAI_API_KEY` in the environment. Fixtures without a PDF are skipped with a warning.
