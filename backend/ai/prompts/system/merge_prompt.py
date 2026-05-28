"""
Merge agent system prompt for combining batch partial extractions.
"""

from ai.prompts.builders.prompt_builder import build_merge_system_prompt

MERGE_SYSTEM_PROMPT = build_merge_system_prompt()

__all__ = ["MERGE_SYSTEM_PROMPT"]
