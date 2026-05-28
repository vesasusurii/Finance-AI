"""Reusable prompt sections shared across all document types."""

from ai.prompts.shared.examples import GOLDEN_EXAMPLES
from ai.prompts.shared.field_rules import FIELD_RULES
from ai.prompts.shared.json_schema import JSON_KEYS, OUTPUT_EXAMPLE, build_json_schema
from ai.prompts.shared.multilingual_labels import MULTILINGUAL_LABELS
from ai.prompts.shared.quality_guidance import QUALITY_GUIDANCE
from ai.prompts.shared.scan_strategy import VISUAL_SCAN_STRATEGY

__all__ = [
    "GOLDEN_EXAMPLES",
    "FIELD_RULES",
    "JSON_KEYS",
    "OUTPUT_EXAMPLE",
    "build_json_schema",
    "MULTILINGUAL_LABELS",
    "QUALITY_GUIDANCE",
    "VISUAL_SCAN_STRATEGY",
]
