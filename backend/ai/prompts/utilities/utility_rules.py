"""
Composed utility document rules (KESCO, water, debt).

Assembles preamble and per-utility sections without changing prompt text.
"""

from ai.prompts.utilities.kesco_rules import KESCO_UTILITY_SECTION
from ai.prompts.utilities.pastrimi_rules import PASTRIMI_UTILITY_SECTION
from ai.prompts.utilities.water_rules import WATER_UTILITY_SECTION

UTILITY_PREAMBLE = """
## Utility bill document types (apply BEFORE generic rules)

**CRITICAL — dynamic extraction only:**
- Sample values in this prompt (amounts, reference codes, customer names) illustrate **field location and format shape** only.
- NEVER copy, memorize, or reuse example numbers from training, samples, or prior invoices.
- Every `invoice_number`, `amount`, and `debt` must be read from **the document in front of you**.

First classify the document. Set `document_type` to exactly one of:
- `electricity_kesco` — KESCO / KESI logo, electricity table (energji, kWh, KESCO+KEK debt)
- `water_regional` — Kompania Rajonale e Ujësjellësit / Regional Water Company, water meter (ujë, m³)
- `waste_pastrimi` — Ndërmarrja Regjionale e Mbeturinave **Pastrimi** / KRM, waste collection (Lokali, open area, Total Due)
- `generic` — all other invoices (SaaS, German Rechnung, retail, etc.)

When `document_type` is NOT `generic`, follow the matching section below **instead of** generic amount/issuer rules.

---
""".strip()

UTILITY_DEBT_SECTION = """
### debt field (all document types)

- Separate numeric field for **outstanding balance / prior debt / Borxhi** — never merge into `amount`.
- If no debt line exists on the document → `debt`: null.
- Finance pays `amount` for the current bill; `debt` is informational.
""".strip()


def build_utility_document_rules() -> str:
    """Full utility rules block (identical to legacy _UTILITY_DOCUMENT_RULES)."""
    return f"""{UTILITY_PREAMBLE}

{KESCO_UTILITY_SECTION}

{WATER_UTILITY_SECTION}

{PASTRIMI_UTILITY_SECTION}

{UTILITY_DEBT_SECTION}""".strip()


__all__ = [
    "UTILITY_PREAMBLE",
    "UTILITY_DEBT_SECTION",
    "build_utility_document_rules",
]
