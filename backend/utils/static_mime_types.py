"""MIME types for bundled frontend static assets (Vite / pdf.js).

pdf.js loads its worker as an ES module (``pdf.worker.min-*.mjs``). Browsers
refuse to execute module workers unless the response ``Content-Type`` is
JavaScript. Python's default ``mimetypes`` table and nginx's stock
``mime.types`` omit ``.mjs``, so both fall back to
``application/octet-stream`` and PDF preview fails in production with::

    Failed to load module script: server responded with a non-JavaScript
    MIME type "application/octet-stream"

Register these mappings at application startup before ``StaticFiles`` /
``FileResponse`` serve ``/assets/*``.
"""

from __future__ import annotations

import mimetypes


def register_frontend_static_mime_types() -> None:
    mimetypes.add_type("text/javascript", ".mjs")
    mimetypes.add_type("text/javascript", ".js")
