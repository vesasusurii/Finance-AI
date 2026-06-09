"""Escape SQL ILIKE wildcard characters in user search terms."""


def escape_ilike_pattern(term: str) -> str:
    return (
        term.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )
