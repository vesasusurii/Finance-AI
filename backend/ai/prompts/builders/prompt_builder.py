"""
Prompt assembly — composes system prompts from shared and utility modules.

No extraction logic here; only joins pre-defined text blocks in a fixed order.
"""

from ai.prompts.document_types.rules import build_document_type_rules
from ai.prompts.shared.examples import GOLDEN_EXAMPLES
from ai.prompts.shared.field_rules import FIELD_RULES
from ai.prompts.shared.json_schema import OUTPUT_EXAMPLE, build_json_schema
from ai.prompts.shared.multilingual_labels import MULTILINGUAL_LABELS
from ai.prompts.shared.quality_guidance import QUALITY_GUIDANCE
from ai.prompts.shared.scan_strategy import VISUAL_SCAN_STRATEGY
from ai.prompts.utilities.utility_rules import build_utility_document_rules
from core.document_categories import DocumentCategory

SECTION_SEPARATOR = "\n\n---\n\n"


def join_sections(*sections: str) -> str:
    """Join non-empty sections with the standard prompt divider."""
    return SECTION_SEPARATOR.join(s for s in sections if s)


def _typed_rules_section(
    document_category: DocumentCategory | None,
    *,
    legacy_include_utility: bool,
) -> str:
    if document_category is not None:
        return build_document_type_rules(document_category)
    if legacy_include_utility:
        return build_utility_document_rules()
    return ""


def build_vision_system_prompt(
    document_category: DocumentCategory | None = None,
    *,
    legacy_include_utility: bool = True,
) -> str:
    """Single-page / full-document Vision OCR system prompt."""
    header = """You are the invoice OCR and data extraction system for Borek Finance (Kosovo).
You receive document images — PDF pages rasterised to JPEG, or direct JPEG/PNG uploads.
You may also receive supplemental text extracted from the PDF text layer — use it to cross-check fields.

Your job: read each image with maximum precision and return structured JSON.

Never hardcode field values from examples — especially `invoice_number`, `amount`, and `debt`. Examples teach patterns and locations only; each document has unique values."""

    typed_rules = _typed_rules_section(
        document_category,
        legacy_include_utility=legacy_include_utility,
    )

    tail = f"{build_json_schema()}\n\n{OUTPUT_EXAMPLE}\n"

    return join_sections(
        header,
        VISUAL_SCAN_STRATEGY,
        MULTILINGUAL_LABELS,
        FIELD_RULES,
        QUALITY_GUIDANCE,
        GOLDEN_EXAMPLES,
        typed_rules,
        tail,
    )


def build_batch_system_prompt(
    document_category: DocumentCategory | None = None,
    *,
    legacy_include_utility: bool = True,
) -> str:
    """Multi-page batch extraction system prompt."""
    header = """You are the invoice OCR system for Borek Finance.
You are processing a PAGE RANGE of a longer multi-page invoice — not the complete document.

Your task: extract only the fields visible on the pages you receive. Set any field to null if it does not appear on these specific pages. Do NOT invent or carry forward values from imagined other pages."""

    batch_rules = """## Batch-mode specific rules

- **Header pages (usually page 1):** will contain name_of_company, address_of_company, invoice_number, invoice_date, client block.
- **Middle pages:** usually line items only → null for most fields; capture line items in internal_note_description.
- **Last page:** usually contains totals, Për pagesë, VAT summary, IBAN. Extract amount, currency, account_details here.
- If you see a partial total that is clearly a sub-total (not final): set amount to null and note the sub-total in internal_note_description.
- Never sum values across pages to derive amount.
- For KESCO / water / Pastrimi utility bills: set `document_type`, apply utility amount/debt rules per document type."""

    tail = f"{build_json_schema()}\n\n{OUTPUT_EXAMPLE}\n"

    typed_rules = _typed_rules_section(
        document_category,
        legacy_include_utility=legacy_include_utility,
    )

    return join_sections(
        header,
        VISUAL_SCAN_STRATEGY,
        MULTILINGUAL_LABELS,
        FIELD_RULES,
        QUALITY_GUIDANCE,
        batch_rules,
        typed_rules,
        tail,
    )


def build_merge_system_prompt() -> str:
    """Merge partial batch JSON extractions into one final result."""
    header = """You are a data merge agent for Borek Finance invoice extraction.

You receive multiple partial JSON extractions, one per page-batch of a multi-page invoice.
Your task: produce ONE final, complete, and accurate JSON by merging all partials."""

    merge_rules = """## Merge rules (apply in order)

### name_of_company, address_of_company, invoice_number, invoice_date
- Take from the EARLIEST partial where the field is non-null (header pages have this).
- If two partials have different non-null values: trust the earlier page. Note conflict in internal_note_description.

### amount, debt, currency
- If `document_type` is `electricity_kesco` or `water_regional`: apply utility merge rules — `amount` from Bill amount row only, `debt` from Borxhi/Total debt lines only (never combine).
- If `document_type` is `waste_pastrimi`: `amount` from **Total Due** / **Gjithsej borxhi**; `debt` from **Previous due** line if present.
- Generic: take `amount` from the partial that shows "Për pagesë" / "For payment" / "Grand total" — typically the LAST partial.
- `debt`: take the maximum non-null debt from any partial (utility bills usually one page). Never add debt to amount.
- Never sum partial amounts together.
- If no partial has amount: null.

### account_details
- Merge all non-null IBAN / bank detail strings from all partials, deduplicate, join with " | ".

### internal_note_description
- Concatenate unique line-item descriptions from all partials. Separate with "; ".
- Remove duplicates. Keep concise (max 3 sentences).

### client_employee_related
- Take from any partial where a person name is present. If conflict: take earliest.
- If all partials are null or empty: **`Borek Solutions`**.

### category
- If all partials agree: use that category.
- If partials disagree: use the value from the partial with the highest confidence_score.

### confidence_score
- Final score = average of all partial confidence_scores, then reduce by 0.05 per null critical field.
- Critical fields: invoice_number, amount, invoice_date, name_of_company.

### needs_review
- true if ANY partial had needs_review true, OR if any critical field is still null after merge."""

    tail = f"{build_json_schema()}\n\nOutput one JSON object only. No explanation.\n"

    return join_sections(header, merge_rules, FIELD_RULES, tail)


__all__ = [
    "SECTION_SEPARATOR",
    "join_sections",
    "build_vision_system_prompt",
    "build_batch_system_prompt",
    "build_merge_system_prompt",
]
