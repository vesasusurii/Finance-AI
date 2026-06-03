from utils.openai_chat import chat_completion_kwargs, is_reasoning_model


def test_is_reasoning_model():
    assert is_reasoning_model("gpt-5-mini")
    assert is_reasoning_model("openai/gpt-5")
    assert is_reasoning_model("o4-mini")
    assert not is_reasoning_model("gpt-4o-mini")
    assert not is_reasoning_model("gpt-4o")


def test_gpt5_uses_max_completion_tokens():
    kwargs = chat_completion_kwargs(
        "gpt-5-mini",
        max_output_tokens=16000,
        temperature=0,
        response_format={"type": "json_object"},
    )
    assert kwargs["max_completion_tokens"] == 16000
    assert "max_tokens" not in kwargs
    assert "temperature" not in kwargs
    assert kwargs["response_format"] == {"type": "json_object"}


def test_gpt4o_uses_max_tokens_and_temperature():
    kwargs = chat_completion_kwargs(
        "gpt-4o-mini",
        max_output_tokens=1800,
        temperature=0,
    )
    assert kwargs["max_tokens"] == 1800
    assert kwargs["temperature"] == 0
    assert "max_completion_tokens" not in kwargs
