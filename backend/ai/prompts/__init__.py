"""
Invoice OCR prompt package for Borek Finance.

Import system prompts from here; version is selected via CURRENT_PROMPT_VERSION.
"""

from ai.prompts.versions import v1

CURRENT_PROMPT_VERSION = "v1"

VISION_SYSTEM_PROMPT = v1.VISION_SYSTEM_PROMPT
BATCH_SYSTEM_PROMPT = v1.BATCH_SYSTEM_PROMPT
MERGE_SYSTEM_PROMPT = v1.MERGE_SYSTEM_PROMPT

__all__ = [
    "CURRENT_PROMPT_VERSION",
    "VISION_SYSTEM_PROMPT",
    "BATCH_SYSTEM_PROMPT",
    "MERGE_SYSTEM_PROMPT",
]
