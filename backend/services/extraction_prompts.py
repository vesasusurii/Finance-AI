"""
Backward-compatible re-exports for invoice OCR prompts.

Prefer: ``from ai.prompts import VISION_SYSTEM_PROMPT, ...``
"""

from ai.prompts import (
    BATCH_SYSTEM_PROMPT,
    CURRENT_PROMPT_VERSION,
    MERGE_SYSTEM_PROMPT,
    VISION_SYSTEM_PROMPT,
)

__all__ = [
    "BATCH_SYSTEM_PROMPT",
    "CURRENT_PROMPT_VERSION",
    "MERGE_SYSTEM_PROMPT",
    "VISION_SYSTEM_PROMPT",
]
