"""OpenAI Chat Completions parameter compatibility across model families."""

from __future__ import annotations

# Reasoning / GPT-5 family: max_completion_tokens, no temperature control.
_REASONING_PREFIXES = ("o1", "o3", "o4", "gpt-5")


def _model_base_name(model: str) -> str:
    return model.lower().split("/")[-1].strip()


def is_reasoning_model(model: str) -> bool:
    name = _model_base_name(model)
    return any(name.startswith(prefix) for prefix in _REASONING_PREFIXES)


def chat_completion_kwargs(
    model: str,
    *,
    max_output_tokens: int | None = None,
    temperature: float | None = 0,
    response_format: dict | None = None,
) -> dict:
    """
    Build kwargs for chat.completions.create that work across GPT-4 and GPT-5/o-series.

    GPT-5 and reasoning models require max_completion_tokens and reject temperature≠1.
    """
    kwargs: dict = {}

    if max_output_tokens is not None:
        if is_reasoning_model(model):
            kwargs["max_completion_tokens"] = max_output_tokens
        else:
            kwargs["max_tokens"] = max_output_tokens

    if temperature is not None and not is_reasoning_model(model):
        kwargs["temperature"] = temperature

    if response_format is not None:
        kwargs["response_format"] = response_format

    return kwargs
