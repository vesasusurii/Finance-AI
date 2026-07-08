import base64
import hashlib
from pathlib import Path

import pytest


def test_theme_init_is_theme_only() -> None:
    theme_init_path = Path(__file__).resolve().parents[2] / "frontend" / "public" / "theme-init.js"
    if not theme_init_path.is_file():
        pytest.skip("frontend tree is not mounted in the backend container")

    theme_init = theme_init_path.read_text(encoding="utf-8")
    assert "localStorage" in theme_init
    assert "setAttribute" not in theme_init


def test_csp_conf_includes_inline_polyfill_hash() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    inline_path = repo_root / "frontend" / "scripts" / "csp-polyfill-inline.js"
    csp_path = repo_root / "infra" / "nginx" / "csp.conf"
    if not inline_path.is_file() or not csp_path.is_file():
        pytest.skip("frontend/infra tree is not mounted in the backend container")

    inline_script = inline_path.read_text(encoding="utf-8").strip()
    digest = hashlib.sha256(inline_script.encode("utf-8")).digest()
    expected = f"'sha256-{base64.b64encode(digest).decode('ascii')}'"
    csp_conf = csp_path.read_text(encoding="utf-8")
    assert expected in csp_conf
