"""
Batch (multi-page page-range) system prompt for OpenAI invoice OCR.
"""

from ai.prompts.builders.prompt_builder import build_batch_system_prompt

BATCH_SYSTEM_PROMPT = build_batch_system_prompt()

__all__ = ["BATCH_SYSTEM_PROMPT"]
