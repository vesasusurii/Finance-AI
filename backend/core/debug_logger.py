"""
Central debug logger for Borek Finance backend.

Provides:
- `setup_debug_logging()`        — call once on app startup
- `get_logger(name)`             — namespaced logger (writes to stdout + file)
- `@debug_trace`                 — decorator that logs entry / exit / exception
                                    of any sync or async function, gated by DEBUG
- `log_typed_fields(log, ...)`   — pretty datatype-aware logging used by the
                                    OCR and matching pipelines (per request)
- `format_typed_value(value)`    — "<repr> (TypeName, len=N)" helper

All log records go to stdout (so they appear in `docker logs / docker compose
logs -f backend`) AND to a rotating file (so they persist across container
restarts). Both sinks are toggled together via the `DEBUG` env var.

The decorator is intentionally a no-op when DEBUG=false so it is safe to apply
to hot paths in production.
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import logging
import os
import sys
from datetime import date, datetime
from decimal import Decimal
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Callable

# ─────────────────────────────────────────────────────────────────────────────
# Module state
# ─────────────────────────────────────────────────────────────────────────────

_DEBUG_ENABLED: bool = False
_INITIALISED: bool = False
_ROOT_NAMESPACE: str = "borek"
_TRACE_NAMESPACE: str = f"{_ROOT_NAMESPACE}.trace"

# Truncate giant strings/bytes in log lines so a single OCR call does not
# flood the terminal. Override via DEBUG_MAX_VALUE_CHARS.
_DEFAULT_MAX_VALUE_CHARS = 400


def is_debug_enabled() -> bool:
    return _DEBUG_ENABLED


# ─────────────────────────────────────────────────────────────────────────────
# Setup
# ─────────────────────────────────────────────────────────────────────────────


def setup_debug_logging() -> None:
    """
    Configure stdout + rotating file handlers on the `borek` namespace.

    Safe to call multiple times; subsequent calls are no-ops. Reads:
      DEBUG                 - "true"/"1"/"yes" enables verbose trace logs
      LOG_LEVEL             - base level when DEBUG=false (default INFO)
      DEBUG_LOG_DIR         - directory to write log files (default /var/log/borek)
      DEBUG_LOG_FILE        - filename (default backend-debug.log)
      DEBUG_LOG_MAX_BYTES   - max file size before rotation (default 10 MB)
      DEBUG_LOG_BACKUPS     - rotated files to keep (default 5)
      DEBUG_MAX_VALUE_CHARS - truncate values longer than this (default 400)
    """
    global _DEBUG_ENABLED, _INITIALISED

    debug_flag = os.environ.get("DEBUG", "false").strip().lower()
    _DEBUG_ENABLED = debug_flag in ("1", "true", "yes", "on")

    base_level_name = os.environ.get("LOG_LEVEL", "info").upper()
    base_level = getattr(logging, base_level_name, logging.INFO)
    effective_level = logging.DEBUG if _DEBUG_ENABLED else base_level

    root_logger = logging.getLogger(_ROOT_NAMESPACE)
    root_logger.setLevel(effective_level)
    root_logger.propagate = False

    if _INITIALISED:
        for handler in root_logger.handlers:
            handler.setLevel(effective_level)
        return

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream = sys.stdout
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        pass
    stream_handler = logging.StreamHandler(stream=stream)
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(effective_level)
    root_logger.addHandler(stream_handler)

    log_dir = Path(os.environ.get("DEBUG_LOG_DIR", "/var/log/borek"))
    log_file_name = os.environ.get("DEBUG_LOG_FILE", "backend-debug.log")
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        max_bytes = int(os.environ.get("DEBUG_LOG_MAX_BYTES", str(10 * 1024 * 1024)))
        backups = int(os.environ.get("DEBUG_LOG_BACKUPS", "5"))
        file_handler = RotatingFileHandler(
            filename=str(log_dir / log_file_name),
            maxBytes=max_bytes,
            backupCount=backups,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(effective_level)
        root_logger.addHandler(file_handler)
    except OSError as exc:
        root_logger.warning(
            "Could not create debug log file at %s: %s — stdout-only.",
            log_dir / log_file_name,
            exc,
        )

    logging.getLogger().setLevel(base_level)

    _INITIALISED = True
    root_logger.info(
        "debug_logger initialised (DEBUG=%s, level=%s, file=%s)",
        _DEBUG_ENABLED,
        logging.getLevelName(effective_level),
        log_dir / log_file_name,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Logger factory
# ─────────────────────────────────────────────────────────────────────────────


def get_logger(name: str) -> logging.Logger:
    """Return a logger under the `borek.*` namespace."""
    if not name.startswith(_ROOT_NAMESPACE):
        name = f"{_ROOT_NAMESPACE}.{name}"
    return logging.getLogger(name)


# ─────────────────────────────────────────────────────────────────────────────
# Datatype-aware formatting
# ─────────────────────────────────────────────────────────────────────────────


def _max_chars() -> int:
    try:
        return int(os.environ.get("DEBUG_MAX_VALUE_CHARS", str(_DEFAULT_MAX_VALUE_CHARS)))
    except ValueError:
        return _DEFAULT_MAX_VALUE_CHARS


def _truncate(text: str, limit: int | None = None) -> str:
    cap = limit or _max_chars()
    if len(text) <= cap:
        return text
    return f"{text[:cap]}...[+{len(text) - cap} chars]"


def format_typed_value(value: Any) -> str:
    """
    Render a value as `<repr> (TypeName[, len=N])` for debug output.

    Long strings, bytes and collections are truncated so the docker terminal
    stays readable. Bytes are reported by size, never by content.
    """
    type_name = type(value).__name__

    if value is None:
        return "None (NoneType)"
    if isinstance(value, bool):
        return f"{value} ({type_name})"
    if isinstance(value, (int, float, Decimal)):
        return f"{value} ({type_name})"
    if isinstance(value, (datetime, date)):
        return f"{value.isoformat()} ({type_name})"
    if isinstance(value, bytes):
        return f"<{len(value)} bytes> ({type_name})"
    if isinstance(value, str):
        return f"'{_truncate(value)}' ({type_name}, len={len(value)})"
    if isinstance(value, (list, tuple, set)):
        sample = _truncate(repr(value))
        return f"{sample} ({type_name}, len={len(value)})"
    if isinstance(value, dict):
        sample = _truncate(repr(value))
        return f"{sample} ({type_name}, len={len(value)})"
    if hasattr(value, "model_dump"):
        try:
            sample = _truncate(repr(value.model_dump()))
            return f"{sample} ({type_name}=Pydantic)"
        except Exception:
            pass
    return f"{_truncate(repr(value))} ({type_name})"


def log_typed_fields(
    logger: logging.Logger,
    label: str,
    obj: Any,
    *,
    level: int = logging.DEBUG,
) -> None:
    """
    Log every field of a Pydantic model / dataclass / dict / object as
    `  field_name = <repr> (TypeName)`. Used by the OCR and matching
    pipelines to make extracted data fully traceable.
    """
    if not logger.isEnabledFor(level):
        return

    if hasattr(obj, "model_dump"):
        try:
            data = obj.model_dump()
        except Exception:
            data = {"<unrepr>": obj}
    elif hasattr(obj, "__dict__") and not isinstance(obj, type):
        data = {k: v for k, v in vars(obj).items() if not k.startswith("_")}
    elif isinstance(obj, dict):
        data = obj
    else:
        data = {"value": obj}

    logger.log(level, "-- %s (%s) --", label, type(obj).__name__)
    if not data:
        logger.log(level, "  (no fields)")
        return
    for key, value in data.items():
        logger.log(level, "  %s = %s", key, format_typed_value(value))


# ─────────────────────────────────────────────────────────────────────────────
# Tracing decorator
# ─────────────────────────────────────────────────────────────────────────────


def _format_args(args: tuple, kwargs: dict, skip_first: bool) -> str:
    parts: list[str] = []
    arg_iter = list(args)
    if skip_first and arg_iter:
        arg_iter = arg_iter[1:]
    for value in arg_iter:
        parts.append(format_typed_value(value))
    for key, value in kwargs.items():
        parts.append(f"{key}={format_typed_value(value)}")
    return ", ".join(parts) if parts else "(none)"


def debug_trace(func: Callable) -> Callable:
    """
    Decorator: logs entry, exit (with return-type info) and exceptions of
    `func` at DEBUG level when the global DEBUG flag is on. Becomes a true
    no-op when DEBUG is off, so the call overhead in production is one
    boolean check.

    Works with both regular and `async def` callables. The first positional
    argument is suppressed when it is `self` or `cls` to keep log lines
    clean.
    """
    qualname = getattr(func, "__qualname__", func.__name__)
    module = getattr(func, "__module__", "")
    logger = logging.getLogger(f"{_TRACE_NAMESPACE}.{module}")

    try:
        sig = inspect.signature(func)
        first_param = next(iter(sig.parameters), None)
    except (TypeError, ValueError):
        first_param = None
    skip_first = first_param in ("self", "cls")

    if asyncio.iscoroutinefunction(func):

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            if not _DEBUG_ENABLED:
                return await func(*args, **kwargs)
            logger.debug(
                ">> %s(%s)", qualname, _format_args(args, kwargs, skip_first)
            )
            try:
                result = await func(*args, **kwargs)
            except Exception as exc:
                logger.exception(
                    "!! %s raised %s: %s", qualname, type(exc).__name__, exc
                )
                raise
            logger.debug("<< %s -> %s", qualname, format_typed_value(result))
            return result

        return async_wrapper

    @functools.wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        if not _DEBUG_ENABLED:
            return func(*args, **kwargs)
        logger.debug(
            ">> %s(%s)", qualname, _format_args(args, kwargs, skip_first)
        )
        try:
            result = func(*args, **kwargs)
        except Exception as exc:
            logger.exception(
                "!! %s raised %s: %s", qualname, type(exc).__name__, exc
            )
            raise
        logger.debug("<< %s -> %s", qualname, format_typed_value(result))
        return result

    return sync_wrapper


__all__ = [
    "setup_debug_logging",
    "is_debug_enabled",
    "get_logger",
    "debug_trace",
    "log_typed_fields",
    "format_typed_value",
]
