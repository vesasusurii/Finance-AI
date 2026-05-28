from pathlib import Path

from fastapi import UploadFile

from core.debug_logger import debug_trace, get_logger
from core.exceptions import ExcelParseError
from repositories.bank_statement_repository import BankStatementRepository
from repositories.bank_transaction_repository import BankTransactionRepository
from repositories.upload_repository import UploadRepository
from schemas.auth import UserContext
from schemas.bank_statement import (
    BankStatementUploadResponse,
    BankTransactionPreview,
)
from utils.bank_excel_parser import parse_bank_statement_excel
from utils.file_storage import get_file_path, save_upload

logger = get_logger(__name__)

ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".xlsm"}
ALLOWED_MIME = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
}


class BankStatementService:
    def __init__(
        self,
        upload_repo: UploadRepository,
        statement_repo: BankStatementRepository,
        transaction_repo: BankTransactionRepository,
    ) -> None:
        self._upload_repo = upload_repo
        self._statement_repo = statement_repo
        self._transaction_repo = transaction_repo

    @debug_trace
    async def upload(
        self, file: UploadFile, user: UserContext
    ) -> BankStatementUploadResponse:
        filename = file.filename or "statement.xlsx"
        ext = Path(filename).suffix.lower()
        logger.debug(
            "Bank statement upload start: filename=%r (str) ext=%r (str) user_id=%d (int)",
            filename, ext, user.user_id,
        )
        if ext not in ALLOWED_EXTENSIONS:
            raise ExcelParseError(
                "Unsupported file type. Upload .xlsx or .xls."
            )

        storage_path = await save_upload(file, "bank_statements")
        upload_row = await self._upload_repo.create(
            file_kind="bank_statement",
            filename=filename,
            storage_path=storage_path,
            mime_type=file.content_type,
            user_id=user.user_id,
            processing_status="processing",
        )

        try:
            data = get_file_path(storage_path).read_bytes()
            logger.debug(
                "Read bank Excel bytes: size=%d (%s)", len(data), type(data).__name__
            )
            parsed_rows = parse_bank_statement_excel(data, filename)
            logger.debug(
                "Parsed bank rows: count=%d (%s)",
                len(parsed_rows), type(parsed_rows).__name__,
            )
        except ExcelParseError:
            await self._upload_repo.update_status(upload_row.id, "failed")
            raise
        except Exception as exc:
            await self._upload_repo.update_status(upload_row.id, "failed")
            raise ExcelParseError(str(exc)) from exc

        row_dicts = [
            {
                "transaction_date": r.transaction_date,
                "debited_amount": r.debited_amount,
                "credited_amount": r.credited_amount,
                "transaction_type": r.transaction_type,
                "comment": r.comment,
                "detected_invoice_numbers": r.detected_invoice_numbers,
            }
            for r in parsed_rows
        ]

        statement = await self._statement_repo.create(
            source_file_id=upload_row.id,
            uploaded_by=user.user_id,
            row_count=len(row_dicts),
            processing_status="processed",
        )
        await self._transaction_repo.create_bulk(statement.id, row_dicts)
        await self._upload_repo.update_status(upload_row.id, "processed")

        preview = [
            BankTransactionPreview(
                transaction_date=r.transaction_date,
                debited_amount=r.debited_amount,
                credited_amount=r.credited_amount,
                transaction_type=r.transaction_type,
                comment=r.comment,
                detected_invoice_numbers=r.detected_invoice_numbers,
            )
            for r in parsed_rows[:10]
        ]

        unparsed_date_rows = sum(
            1 for r in parsed_rows if r.transaction_date is None
        )
        if unparsed_date_rows:
            logger.warning(
                "Bank upload %s: %d/%d rows have unparsable transaction_date "
                "— matching will skip them with reason=missing_transaction_date",
                filename, unparsed_date_rows, len(parsed_rows),
            )

        return BankStatementUploadResponse(
            bank_statement_id=statement.id,
            row_count=len(row_dicts),
            processing_status="processed",
            unparsed_date_rows=unparsed_date_rows,
            preview=preview,
        )
