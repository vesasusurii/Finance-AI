from pathlib import Path

from datetime import date, datetime, timezone

from fastapi import HTTPException, UploadFile

from core.debug_logger import debug_trace, get_logger
from core.exceptions import ExcelParseError
from core.invoice_access import upload_owner_user_id
from repositories.bank_statement_repository import BankStatementRepository
from repositories.bank_transaction_repository import BankTransactionRepository
from repositories.review_repository import ReviewRepository
from repositories.upload_repository import UploadRepository
from schemas.auth import UserContext
from schemas.bank_statement import (
    BankStatementReparseResponse,
    BankStatementUploadResponse,
    BankTransactionPreview,
)
from utils.bank_excel_parser import (
    dedupe_parsed_rows,
    extract_statement_date,
    parse_bank_statement_excel,
)
from utils.file_storage import delete_storage_object, read_bytes, save_bytes

logger = get_logger(__name__)

ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".xlsm"}


class BankStatementService:
    def __init__(
        self,
        upload_repo: UploadRepository,
        statement_repo: BankStatementRepository,
        transaction_repo: BankTransactionRepository,
        review_repo: ReviewRepository,
    ) -> None:
        self._upload_repo = upload_repo
        self._statement_repo = statement_repo
        self._transaction_repo = transaction_repo
        self._review_repo = review_repo

    @debug_trace
    async def upload(
        self, file: UploadFile, user: UserContext
    ) -> BankStatementUploadResponse:
        filename = file.filename or "statement.xlsx"
        ext = Path(filename).suffix.lower()
        logger.debug(
            "Bank statement upload start: filename=%r ext=%r user_id=%d",
            filename,
            ext,
            user.user_id,
        )
        if ext not in ALLOWED_EXTENSIONS:
            raise ExcelParseError(
                "Unsupported file type. Upload .xlsx or .xls."
            )

        content = await file.read()
        storage_path, file_size = await save_bytes(
            content,
            user_id=user.user_id,
            filename=filename,
            mime_type=file.content_type,
        )
        upload_row = await self._upload_repo.create(
            file_kind="bank_statement",
            filename=filename,
            storage_path=storage_path,
            mime_type=file.content_type,
            user_id=user.user_id,
            processing_status="processing",
            file_size=file_size,
        )

        try:
            data = await read_bytes(storage_path)
            parsed_rows = parse_bank_statement_excel(data, filename)
            parsed_rows, duplicate_rows_skipped = dedupe_parsed_rows(parsed_rows)
            if not parsed_rows:
                raise ExcelParseError(
                    "No transaction rows found after removing duplicates."
                )
            statement_date = extract_statement_date(filename, parsed_rows)
        except ExcelParseError:
            await self._upload_repo.update_status(upload_row.id, "failed")
            raise
        except ValueError as exc:
            await self._upload_repo.update_status(upload_row.id, "failed")
            raise ExcelParseError(str(exc)) from exc
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

        try:
            statement = await self._statement_repo.create(
                source_file_id=upload_row.id,
                uploaded_by=user.user_id,
                row_count=len(row_dicts),
                statement_date=statement_date,
                processing_status="processed",
            )
        except ValueError as exc:
            await self._upload_repo.update_status(upload_row.id, "failed")
            raise ExcelParseError(str(exc)) from exc

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
                "Bank upload %s: %d/%d rows have unparsable transaction_date",
                filename,
                unparsed_date_rows,
                len(parsed_rows),
            )

        return BankStatementUploadResponse(
            bank_statement_id=statement.id,
            statement_date=statement_date,
            row_count=len(row_dicts),
            processing_status="processed",
            unparsed_date_rows=unparsed_date_rows,
            duplicate_rows_skipped=duplicate_rows_skipped,
            preview=preview,
        )

    @debug_trace
    async def reparse_statement(
        self, statement_id: int, user: UserContext
    ) -> BankStatementReparseResponse:
        owner = upload_owner_user_id(user)
        statement = await self._statement_repo.get(
            statement_id, owner_user_id=owner
        )
        if statement is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "bank_statement_not_found",
                    "message": "Bank statement not found.",
                },
            )

        upload = await self._upload_repo.get(statement.source_file_id)
        if upload is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "source_file_not_found",
                    "message": "Original bank file is missing.",
                },
            )

        data = await read_bytes(upload.storage_path)
        try:
            parsed_rows = parse_bank_statement_excel(data, upload.original_filename)
            parsed_rows, _duplicate_rows_skipped = dedupe_parsed_rows(parsed_rows)
        except ExcelParseError:
            raise
        except ValueError as exc:
            raise ExcelParseError(str(exc)) from exc
        except Exception as exc:
            raise ExcelParseError(str(exc)) from exc

        existing = await self._transaction_repo.list_for_statement(statement_id)
        if len(existing) != len(parsed_rows):
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "row_count_mismatch",
                    "message": (
                        f"Re-parse found {len(parsed_rows)} rows but the statement "
                        f"has {len(existing)} stored transactions. Re-upload the file "
                        "instead."
                    ),
                },
            )

        now = datetime.now(timezone.utc)
        rows_updated = 0
        dates_fixed = 0
        review_tasks_resolved = 0

        for txn_row, parsed in zip(existing, parsed_rows, strict=True):
            changed = False
            if txn_row.transaction_date != parsed.transaction_date:
                had_date = txn_row.transaction_date is not None
                txn_row.transaction_date = parsed.transaction_date
                changed = True
                if not had_date and parsed.transaction_date is not None:
                    dates_fixed += 1
                    if txn_row.reconciliation_status == "needs_review":
                        txn_row.reconciliation_status = "pending"
                    review_tasks_resolved += (
                        await self._review_repo.resolve_missing_transaction_date_tasks(
                            txn_row.id, now
                        )
                    )
            for field, value in (
                ("debited_amount", parsed.debited_amount),
                ("credited_amount", parsed.credited_amount),
                ("transaction_type", parsed.transaction_type),
                ("comment", parsed.comment),
                ("detected_invoice_numbers", parsed.detected_invoice_numbers),
            ):
                if getattr(txn_row, field) != value:
                    setattr(txn_row, field, value)
                    changed = True
            if changed:
                rows_updated += 1

        unparsed_date_rows = sum(
            1 for r in parsed_rows if r.transaction_date is None
        )
        if unparsed_date_rows:
            logger.warning(
                "Bank re-parse statement_id=%d: %d/%d rows still lack transaction_date",
                statement_id,
                unparsed_date_rows,
                len(parsed_rows),
            )

        return BankStatementReparseResponse(
            bank_statement_id=statement_id,
            rows_updated=rows_updated,
            dates_fixed=dates_fixed,
            unparsed_date_rows=unparsed_date_rows,
            review_tasks_resolved=review_tasks_resolved,
        )

    @debug_trace
    async def delete_statement(
        self, statement_id: int, user: UserContext
    ) -> None:
        from core.invoice_access import upload_owner_user_id

        owner = upload_owner_user_id(user)
        row = await self._statement_repo.delete_statement(
            statement_id,
            owner_user_id=owner,
        )
        if row is None:
            from fastapi import HTTPException

            raise HTTPException(
                status_code=404,
                detail={
                    "error": "bank_statement_not_found",
                    "message": "Bank statement not found.",
                },
            )

        upload = await self._upload_repo.get(row.source_file_id)
        if upload:
            try:
                await delete_storage_object(upload.storage_path)
            except (FileNotFoundError, RuntimeError) as exc:
                logger.warning(
                    "Storage cleanup skipped for bank statement upload %s: %s",
                    upload.id,
                    exc,
                )
            await self._upload_repo.delete(upload.id)
