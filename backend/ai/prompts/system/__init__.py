"""Assembled system prompts for each extraction mode."""

from ai.prompts.system.batch_prompt import BATCH_SYSTEM_PROMPT
from ai.prompts.system.merge_prompt import MERGE_SYSTEM_PROMPT
from ai.prompts.system.vision_prompt import VISION_SYSTEM_PROMPT

__all__ = ["BATCH_SYSTEM_PROMPT", "MERGE_SYSTEM_PROMPT", "VISION_SYSTEM_PROMPT"]
