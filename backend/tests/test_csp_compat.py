from pathlib import Path

import pytest


def test_theme_init_includes_react_oninput_csp_polyfill() -> None:
    theme_init_path = Path(__file__).resolve().parents[2] / "frontend" / "public" / "theme-init.js"
    if not theme_init_path.is_file():
        pytest.skip("frontend tree is not mounted in the backend container")

    theme_init = theme_init_path.read_text(encoding="utf-8")
    assert 'defineProperty(document, "oninput"' in theme_init
    assert 'setAttribute("oninput", "return;")' in theme_init
