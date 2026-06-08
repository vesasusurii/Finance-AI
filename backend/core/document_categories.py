"""Invoice document categories for classifier and prompt routing."""

from enum import Enum


class DocumentCategory(str, Enum):
    GENERIC = "generic"
    UTILITY = "utility"
    ALBANIAN_RETAIL = "albanian_retail"
    FREELANCER = "freelancer"
