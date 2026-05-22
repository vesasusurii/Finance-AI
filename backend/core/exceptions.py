"""Application exception hierarchy (doc 6 §7)."""


class AppError(Exception):
    pass


class ExtractionError(AppError):
    pass


class ExcelParseError(AppError):
    pass


class MatchError(AppError):
    pass


class ExportError(AppError):
    pass
