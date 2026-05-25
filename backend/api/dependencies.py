from collections.abc import AsyncGenerator

from fastapi import Depends, Request
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from api.controllers.auth_controller import AuthController
from api.controllers.bank_statement_controller import BankStatementController
from api.controllers.export_controller import ExportController
from api.controllers.invoice_controller import InvoiceController
from config import settings
from db.pool import async_session
from middleware.auth import get_current_user as _get_user_from_request
from repositories.audit_repository import AuditRepository
from repositories.bank_statement_repository import BankStatementRepository
from repositories.bank_transaction_repository import BankTransactionRepository
from repositories.invoice_repository import InvoiceRepository
from repositories.upload_repository import UploadRepository
from repositories.user_repository import UserRepository
from schemas.auth import UserContext
from services.ai_validation_service import AIValidationService
from services.bank_statement_service import BankStatementService
from services.excel_service import ExcelService
from services.invoice_extraction_service import InvoiceExtractionService


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_current_user(request: Request) -> UserContext:
    return _get_user_from_request(request)


def get_openai_client(request: Request) -> AsyncOpenAI:
    client = getattr(request.app.state, "openai_client", None)
    if client is None:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=503,
            detail={
                "error": "openai_not_configured",
                "message": "OPENAI_API_KEY is not set on the server.",
            },
        )
    return client


async def get_user_repo(
    session: AsyncSession = Depends(get_db_session),
) -> UserRepository:
    return UserRepository(session)


async def get_upload_repo(
    session: AsyncSession = Depends(get_db_session),
) -> UploadRepository:
    return UploadRepository(session)


async def get_invoice_repo(
    session: AsyncSession = Depends(get_db_session),
) -> InvoiceRepository:
    return InvoiceRepository(session)


async def get_audit_repo(
    session: AsyncSession = Depends(get_db_session),
) -> AuditRepository:
    return AuditRepository(session)


def get_ai_validation_service() -> AIValidationService:
    return AIValidationService()


def get_excel_service() -> ExcelService:
    return ExcelService()


async def get_invoice_extraction_service(
    upload_repo: UploadRepository = Depends(get_upload_repo),
    invoice_repo: InvoiceRepository = Depends(get_invoice_repo),
    audit_repo: AuditRepository = Depends(get_audit_repo),
    ai_validation: AIValidationService = Depends(get_ai_validation_service),
    openai_client: AsyncOpenAI = Depends(get_openai_client),
) -> InvoiceExtractionService:
    return InvoiceExtractionService(
        upload_repo, invoice_repo, audit_repo, ai_validation, openai_client
    )


async def get_auth_controller(
    user_repo: UserRepository = Depends(get_user_repo),
) -> AuthController:
    return AuthController(user_repo)


async def get_invoice_controller(
    extraction: InvoiceExtractionService = Depends(get_invoice_extraction_service),
    invoice_repo: InvoiceRepository = Depends(get_invoice_repo),
    audit_repo: AuditRepository = Depends(get_audit_repo),
) -> InvoiceController:
    return InvoiceController(extraction, invoice_repo, audit_repo)


async def get_export_controller(
    invoice_repo: InvoiceRepository = Depends(get_invoice_repo),
    excel: ExcelService = Depends(get_excel_service),
) -> ExportController:
    return ExportController(invoice_repo, excel)


async def get_bank_statement_repo(
    session: AsyncSession = Depends(get_db_session),
) -> BankStatementRepository:
    return BankStatementRepository(session)


async def get_bank_transaction_repo(
    session: AsyncSession = Depends(get_db_session),
) -> BankTransactionRepository:
    return BankTransactionRepository(session)


async def get_bank_statement_service(
    upload_repo: UploadRepository = Depends(get_upload_repo),
    statement_repo: BankStatementRepository = Depends(get_bank_statement_repo),
    transaction_repo: BankTransactionRepository = Depends(get_bank_transaction_repo),
) -> BankStatementService:
    return BankStatementService(upload_repo, statement_repo, transaction_repo)


async def get_bank_statement_controller(
    service: BankStatementService = Depends(get_bank_statement_service),
    statement_repo: BankStatementRepository = Depends(get_bank_statement_repo),
    transaction_repo: BankTransactionRepository = Depends(get_bank_transaction_repo),
) -> BankStatementController:
    return BankStatementController(service, statement_repo, transaction_repo)
