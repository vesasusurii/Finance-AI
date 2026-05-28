"""
Guidance for low-quality, skewed, or difficult scans.
"""

QUALITY_GUIDANCE = """
## Handling difficult documents

**Low-quality / faded scans:**
- Read pixel by pixel in high-detail mode. Partially visible characters: guess the most likely character from context (e.g. "lnvoice" → "Invoice").
- For numeric fields (amount, invoice_number): if a digit is ambiguous, prefer the value that makes financial sense given other visible amounts.

**Skewed or rotated images:**
- Read text in its natural orientation. Rotated stamps or watermarks — ignore content inside them.

**Handwritten annotations:**
- If a handwritten number overwrites or supplements a printed amount → use the handwritten value (Finance may have corrected it).
- Handwritten "PAID" or "CANCELLED" stamps → set needs_review true, note in internal_note_description.

**Stamps and seals:**
- Ignore decorative stamps (company logos, "RECEIVED" stamps) for field extraction.
- A stamp that shows a date is NOT the invoice date unless it is in the invoice reference area.

**Multi-column or complex layouts:**
- Read left column, then right column. Do not mix values across columns.

**Watermarks:**
- Ignore text that appears as a semi-transparent background watermark (e.g. "DRAFT", "COPY").

**Noisy backgrounds / poor contrast:**
- Focus on dark, clearly printed text. Tables and borders help identify value positions.
""".strip()

__all__ = ['QUALITY_GUIDANCE']
