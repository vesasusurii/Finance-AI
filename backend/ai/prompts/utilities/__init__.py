"""Utility bill (KESCO, regional water) prompt sections."""

from ai.prompts.utilities.kesco_rules import KESCO_UTILITY_SECTION
from ai.prompts.utilities.pastrimi_rules import PASTRIMI_UTILITY_SECTION
from ai.prompts.utilities.utility_rules import build_utility_document_rules
from ai.prompts.utilities.water_rules import (
    WATER_INVOICE_NUMBER_CRITICAL,
    WATER_UTILITY_SECTION,
)

__all__ = [
    "KESCO_UTILITY_SECTION",
    "PASTRIMI_UTILITY_SECTION",
    "WATER_INVOICE_NUMBER_CRITICAL",
    "WATER_UTILITY_SECTION",
    "build_utility_document_rules",
]
