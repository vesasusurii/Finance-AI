# Invoice OCR prompts

Modular prompt assembly for Borek Finance OpenAI Vision extraction. **Prompt text is unchanged** from the legacy monolithic `services/extraction_prompts.py`; only structure moved.

## Folder structure

```
prompts/
├── __init__.py              # Public API + CURRENT_PROMPT_VERSION
├── shared/                  # Reusable sections (all document types)
│   ├── json_schema.py       # JSON_KEYS, schema block, output example
│   ├── multilingual_labels.py
│   ├── field_rules.py
│   ├── scan_strategy.py
│   ├── quality_guidance.py
│   └── examples.py          # Golden patterns (no hardcoded values)
├── utilities/               # Utility bill rules
│   ├── kesco_rules.py       # KESCO electricity section
│   ├── water_rules.py       # Water bill + CRITICAL invoice_number block
│   ├── pastrimi_rules.py    # Pastrimi / KRM waste (Total Due = amount)
│   └── utility_rules.py     # Composes preamble + all utility sections + debt
├── builders/
│   └── prompt_builder.py    # join_sections + build_*_system_prompt()
├── system/                  # Final system prompts (thin wrappers)
│   ├── vision_prompt.py
│   ├── batch_prompt.py
│   └── merge_prompt.py
└── versions/
    └── v1.py                # Current production bundle
```

## Usage

```python
from ai.prompts import (
    CURRENT_PROMPT_VERSION,
    VISION_SYSTEM_PROMPT,
    BATCH_SYSTEM_PROMPT,
    MERGE_SYSTEM_PROMPT,
)
```

Legacy import still works:

```python
from services.extraction_prompts import VISION_SYSTEM_PROMPT
```

## Adding a new prompt version (v2)

1. Copy `versions/v1.py` to `versions/v2.py` (or point v2 at new builders).
2. Adjust modules under `shared/` or `utilities/` as needed.
3. Add `build_*` functions in `builders/prompt_builder.py` if assembly order changes.
4. Set `CURRENT_PROMPT_VERSION = "v2"` in `prompts/__init__.py` and import from `v2`.
5. Run `python scripts/prompts/verify_prompt_refactor.py` after updating the baseline (or add a v2-specific check).

## Extending utility rules safely

- **KESCO-only changes:** edit `utilities/kesco_rules.py`.
- **Water-only changes:** edit `utilities/water_rules.py` (`WATER_INVOICE_NUMBER_CRITICAL` and/or `WATER_UTILITY_SECTION`).
- **Pastrimi waste-only changes:** edit `utilities/pastrimi_rules.py`.
- **Shared debt / classification preamble:** edit `utilities/utility_rules.py` (`UTILITY_PREAMBLE`, `build_utility_document_rules()`).
- Do **not** duplicate rules in `field_rules.py` unless they apply to generic invoices too.

After edits, restart the backend (or rely on `--reload`) and re-test with sample PDFs.

## Verification

```bash
cd backend
python scripts/prompts/verify_prompt_refactor.py
```

Compares assembled prompts to a saved baseline captured before refactor.

## Module responsibilities

| Module | Responsibility |
|--------|----------------|
| `shared/*` | Labels, field rules, scan order, quality tips, JSON output contract |
| `utilities/*` | KESCO / water document-type rules and invoice_number traps |
| `builders/prompt_builder.py` | Ordered assembly only — no business logic |
| `system/*` | Exported constants used by `invoice_extraction_service` |
| `versions/v1.py` | Pins the active prompt bundle for production |
