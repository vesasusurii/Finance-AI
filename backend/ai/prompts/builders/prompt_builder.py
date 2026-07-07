"""
Prompt assembly — composes system prompts from shared and utility modules.

Production prompts use the minimal blocks in `shared/minimal_prompts.py` to reduce
OpenAI token usage. Utility-specific rules are included only for UTILITY documents.
"""

from ai.prompts.document_types.rules import build_document_type_rules
from ai.prompts.shared.json_schema import build_json_schema
from ai.prompts.shared.minimal_prompts import (
    MINIMAL_BATCH_HEADER,
    MINIMAL_BATCH_RULES,
    MINIMAL_FIELD_RULES,
    MINIMAL_MERGE_HEADER,
    MINIMAL_MERGE_RULES,
    MINIMAL_SCAN_HINT,
    MINIMAL_VISION_HEADER,
)
from core.document_categories import DocumentCategory

SECTION_SEPARATOR = "\n\n---\n\n"


def join_sections(*sections: str) -> str:
    """Join non-empty sections with the standard prompt divider."""
    return SECTION_SEPARATOR.join(s for s in sections if s)


def estimate_prompt_tokens(*texts: str) -> int:
    """Rough token estimate (~4 chars per token) for logging/metrics."""
    combined = "".join(texts)
    if not combined:
        return 0
    return max(1, len(combined) // 4)


def prompt_strategy_label(
    *,
    mode: str,
    document_category: DocumentCategory | None = None,
) -> str:
    """Short label for metrics (e.g. minimal+utility, minimal+batch)."""
    base = "minimal"
    if document_category == DocumentCategory.UTILITY:
        base = f"{base}+utility"
    elif document_category and document_category != DocumentCategory.GENERIC:
        base = f"{base}+{document_category.value}"
    if mode == "batch":
        return f"{base}+batch"
    if mode == "merge":
        return f"{base}+merge"
    if mode == "text_llm":
        return f"{base}+text_llm"
    return base


def _typed_rules_section(document_category: DocumentCategory | None) -> str:
    if document_category is None:
        return ""
    return build_document_type_rules(document_category)


def build_vision_system_prompt(
    document_category: DocumentCategory | None = None,
) -> str:
    """Single-page / full-document Vision OCR system prompt (minimal)."""
    typed_rules = _typed_rules_section(document_category)
    return join_sections(
        MINIMAL_VISION_HEADER,
        MINIMAL_SCAN_HINT,
        MINIMAL_FIELD_RULES,
        typed_rules,
        build_json_schema(),
    )


def build_batch_system_prompt(
    document_category: DocumentCategory | None = None,
) -> str:
    """Multi-page batch extraction system prompt (minimal — no golden examples)."""
    typed_rules = _typed_rules_section(document_category)
    return join_sections(
        MINIMAL_BATCH_HEADER,
        MINIMAL_BATCH_RULES,
        MINIMAL_FIELD_RULES,
        typed_rules,
        build_json_schema(),
    )


def build_merge_system_prompt() -> str:
    """Merge partial batch JSON extractions (minimal — LLM fallback only)."""
    return join_sections(
        MINIMAL_MERGE_HEADER,
        MINIMAL_MERGE_RULES,
        build_json_schema(),
    )


__all__ = [
    "SECTION_SEPARATOR",
    "join_sections",
    "estimate_prompt_tokens",
    "prompt_strategy_label",
    "build_vision_system_prompt",
    "build_batch_system_prompt",
    "build_merge_system_prompt",
]
