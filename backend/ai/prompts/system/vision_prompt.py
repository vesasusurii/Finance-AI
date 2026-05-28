"""
Vision (single-document) system prompt for OpenAI invoice OCR.
"""

from ai.prompts.builders.prompt_builder import build_vision_system_prompt

VISION_SYSTEM_PROMPT = build_vision_system_prompt()

__all__ = ["VISION_SYSTEM_PROMPT"]
