import mimetypes
from pathlib import Path

from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles
from starlette.testclient import TestClient

from utils.static_mime_types import register_frontend_static_mime_types


def test_pdf_worker_mjs_is_javascript() -> None:
    register_frontend_static_mime_types()
    media_type, _encoding = mimetypes.guess_type(
        "/assets/pdf.worker.min-yatZIOMy.mjs",
    )
    assert media_type == "text/javascript"


def test_vite_js_bundle_is_javascript() -> None:
    register_frontend_static_mime_types()
    media_type, _encoding = mimetypes.guess_type("/assets/index-BY3-FvCV.js")
    assert media_type == "text/javascript"


def test_staticfiles_serves_mjs_as_javascript(tmp_path: Path) -> None:
    register_frontend_static_mime_types()
    assets = tmp_path / "assets"
    assets.mkdir()
    worker = assets / "pdf.worker.min-test.mjs"
    worker.write_text("export {};")

    app = Starlette(
        routes=[Mount("/assets", app=StaticFiles(directory=assets), name="assets")],
    )
    client = TestClient(app)
    response = client.get("/assets/pdf.worker.min-test.mjs")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/javascript")
