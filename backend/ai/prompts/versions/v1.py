"""
Prompt bundle v1 — current production prompts.

Add v2.py later with alternate builders; switch CURRENT_PROMPT_VERSION in __init__.py.
"""

from ai.prompts.system.batch_prompt import BATCH_SYSTEM_PROMPT
from ai.prompts.system.merge_prompt import MERGE_SYSTEM_PROMPT
from ai.prompts.system.vision_prompt import VISION_SYSTEM_PROMPT

__all__ = ["VISION_SYSTEM_PROMPT", "BATCH_SYSTEM_PROMPT", "MERGE_SYSTEM_PROMPT"]
