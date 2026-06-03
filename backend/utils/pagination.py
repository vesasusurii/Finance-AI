MAX_PAGE_LIMIT = 200


def normalize_pagination(page: int, limit: int) -> tuple[int, int]:
    """Clamp pagination values after FastAPI has parsed their types."""
    safe_page = max(1, page)
    safe_limit = min(MAX_PAGE_LIMIT, max(1, limit))
    return safe_page, safe_limit
