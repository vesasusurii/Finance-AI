from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, Request
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from api.controllers.admin_controller import AdminController
from api.controllers.audit_controller import AuditController
from api.controllers.auth_controller import AuthController
from api.controllers.bank_statement_controller import BankStatementController
from api.controllers.export_controller import ExportController
from api.controllers.invoice_controller import InvoiceController
from api.controllers.reconciliation_controller import ReconciliationController
from api.controllers.document_controller import DocumentController
from api.controllers.review_controller import ReviewController
from api.controllers.user_controller import UserController
from config import settings
from core.roles import is_admin
from db.pool import async_session
from middleware.auth import get_current_user as _get_user_from_request
from repositories.audit_repository import AuditRepository
from repositories.bank_statement_repository import BankStatementRepository
from repositories.bank_transaction_repository import BankTransactionRepository
from repositories.invoice_access_repository import InvoiceAccessRepository
from repositories.invoice_repository import InvoiceRepository
from repositories.match_repository import MatchRepository
from repositories.report_repository import ReportRepository
from repositories.review_repository import ReviewRepository
from repositories.upload_repository import UploadRepository
from repositories.user_repository import UserRepository
from schemas.auth import UserContext
from services.admin_settings_service import AdminSettingsService
from services.ai_validation_service import AIValidationService
from services.bank_comment_extraction_service import BankCommentExtractionService
from services.bank_statement_service import BankStatementService
from services.document_service import DocumentService
from services.excel_service import ExcelService
from services.export_service import ExportService
from services.invoice_extraction_service import InvoiceExtractionService
from services.matching_service import MatchingService
from services.review_service import ReviewService


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    session = async_session()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


def get_current_user(request: Request) -> UserContext:
    return _get_user_from_request(request)


def require_admin(user: UserContext = Depends(get_current_user)) -> UserContext:
    if not is_admin(user.role):
        raise HTTPException(
            status_code=403,
            detail={
                "error": "forbidden",
                "message": "Admin access required.",
            },
        )
    return user


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


async def get_invoice_access_repo(
    session: AsyncSession = Depends(get_db_session),
) -> InvoiceAccessRepository:
    return InvoiceAccessRepository(session)


async def get_audit_repo(
    session: AsyncSession = Depends(get_db_session),
) -> AuditRepository:
    return AuditRepository(session)


async def get_match_repo(
    session: AsyncSession = Depends(get_db_session),
) -> MatchRepository:
    return MatchRepository(session)


def get_ai_validation_service() -> AIValidationService:
    return AIValidationService()


def get_excel_service() -> ExcelService:
    return ExcelService()


async def get_invoice_extraction_service(
    upload_repo: UploadRepository = Depends(get_upload_repo),
    invoice_repo: InvoiceRepository = Depends(get_invoice_repo),
    invoice_access_repo: InvoiceAccessRepository = Depends(get_invoice_access_repo),
    audit_repo: AuditRepository = Depends(get_audit_repo),
    ai_validation: AIValidationService = Depends(get_ai_validation_service),
    openai_client: AsyncOpenAI = Depends(get_openai_client),
) -> InvoiceExtractionService:
    return InvoiceExtractionService(
        upload_repo,
        invoice_repo,
        invoice_access_repo,
        audit_repo,
        ai_validation,
        openai_client,
    )


def get_admin_settings_service() -> AdminSettingsService:
    return AdminSettingsService()


async def get_admin_controller(
    settings_service: AdminSettingsService = Depends(get_admin_settings_service),
) -> AdminController:
    return AdminController(settings_service)


async def get_audit_controller(
    audit_repo: AuditRepository = Depends(get_audit_repo),
) -> AuditController:
    return AuditController(audit_repo)


async def get_auth_controller(
    user_repo: UserRepository = Depends(get_user_repo),
    audit_repo: AuditRepository = Depends(get_audit_repo),
) -> AuthController:
    return AuthController(user_repo, audit_repo)


async def get_bank_statement_repo(
    session: AsyncSession = Depends(get_db_session),
) -> BankStatementRepository:
    return BankStatementRepository(session)


async def get_user_controller(
    user_repo: UserRepository = Depends(get_user_repo),
    statement_repo: BankStatementRepository = Depends(get_bank_statement_repo),
) -> UserController:
    return UserController(user_repo, statement_repo)


async def get_invoice_controller(
    extraction: InvoiceExtractionService = Depends(get_invoice_extraction_service),
    invoice_repo: InvoiceRepository = Depends(get_invoice_repo),
    invoice_access_repo: InvoiceAccessRepository = Depends(get_invoice_access_repo),
    audit_repo: AuditRepository = Depends(get_audit_repo),
    upload_repo: UploadRepository = Depends(get_upload_repo),
    match_repo: MatchRepository = Depends(get_match_repo),
) -> InvoiceController:
    return InvoiceController(
        extraction,
        invoice_repo,
        invoice_access_repo,
        audit_repo,
        upload_repo,
        match_repo,
    )


async def get_report_repo(
    session: AsyncSession = Depends(get_db_session),
) -> ReportRepository:
    return ReportRepository(session)


async def get_export_service(
    report_repo: ReportRepository = Depends(get_report_repo),
) -> ExportService:
    return ExportService(report_repo)


async def get_export_controller(
    excel: ExcelService = Depends(get_excel_service),
    export_service: ExportService = Depends(get_export_service),
    invoice_repo: InvoiceRepository = Depends(get_invoice_repo),
) -> ExportController:
    return ExportController(excel, export_service, invoice_repo)


async def get_bank_transaction_repo(
    session: AsyncSession = Depends(get_db_session),
) -> BankTransactionRepository:
    return BankTransactionRepository(session)


async def get_review_repo(
    session: AsyncSession = Depends(get_db_session),
) -> ReviewRepository:
    return ReviewRepository(session)


async def get_bank_statement_service(
    upload_repo: UploadRepository = Depends(get_upload_repo),
    statement_repo: BankStatementRepository = Depends(get_bank_statement_repo),
    transaction_repo: BankTransactionRepository = Depends(get_bank_transaction_repo),
    review_repo: ReviewRepository = Depends(get_review_repo),
) -> BankStatementService:
    return BankStatementService(
        upload_repo, statement_repo, transaction_repo, review_repo
    )


async def get_bank_statement_controller(
    service: BankStatementService = Depends(get_bank_statement_service),
    statement_repo: BankStatementRepository = Depends(get_bank_statement_repo),
    transaction_repo: BankTransactionRepository = Depends(get_bank_transaction_repo),
) -> BankStatementController:
    return BankStatementController(service, statement_repo, transaction_repo)


def get_bank_comment_extraction_service(
    request: Request,
) -> BankCommentExtractionService | None:
    """
    Return the LLM-backed bank-comment extractor, or None when the LLM
    fallback is disabled or OpenAI is not configured. The matching service
    treats None as 'regex-only mode'.
    """
    if not settings.bank_comment_use_llm:
        return None
    client = getattr(request.app.state, "openai_client", None)
    if client is None:
        return None
    return BankCommentExtractionService(
        client,
        model=settings.bank_comment_llm_model,
        batch_size=settings.bank_comment_llm_batch_size,
        timeout_seconds=settings.bank_comment_llm_timeout_seconds,
        max_retries=settings.bank_comment_llm_max_retries,
    )


async def get_matching_service(
    invoice_repo: InvoiceRepository = Depends(get_invoice_repo),
    bank_txn_repo: BankTransactionRepository = Depends(get_bank_transaction_repo),
    match_repo: MatchRepository = Depends(get_match_repo),
    review_repo: ReviewRepository = Depends(get_review_repo),
    audit_repo: AuditRepository = Depends(get_audit_repo),
    comment_extractor: BankCommentExtractionService | None = Depends(
        get_bank_comment_extraction_service
    ),
) -> MatchingService:
    return MatchingService(
        invoice_repo,
        bank_txn_repo,
        match_repo,
        review_repo,
        audit_repo,
        comment_extractor=comment_extractor,
    )


async def get_reconciliation_controller(
    matching: MatchingService = Depends(get_matching_service),
    match_repo: MatchRepository = Depends(get_match_repo),
    invoice_repo: InvoiceRepository = Depends(get_invoice_repo),
    statement_repo: BankStatementRepository = Depends(get_bank_statement_repo),
    bank_txn_repo: BankTransactionRepository = Depends(get_bank_transaction_repo),
    audit_repo: AuditRepository = Depends(get_audit_repo),
) -> ReconciliationController:
    return ReconciliationController(
        matching,
        match_repo,
        invoice_repo,
        statement_repo,
        bank_txn_repo,
        audit_repo,
    )


async def get_document_service(
    upload_repo: UploadRepository = Depends(get_upload_repo),
    invoice_repo: InvoiceRepository = Depends(get_invoice_repo),
    extraction: InvoiceExtractionService = Depends(get_invoice_extraction_service),
    openai_client: AsyncOpenAI = Depends(get_openai_client),
) -> DocumentService:
    return DocumentService(upload_repo, invoice_repo, extraction, openai_client)


async def get_document_controller(
    service: DocumentService = Depends(get_document_service),
) -> DocumentController:
    return DocumentController(service)


async def get_review_service(
    review_repo: ReviewRepository = Depends(get_review_repo),
    invoice_repo: InvoiceRepository = Depends(get_invoice_repo),
    bank_txn_repo: BankTransactionRepository = Depends(get_bank_transaction_repo),
    audit_repo: AuditRepository = Depends(get_audit_repo),
    statement_repo: BankStatementRepository = Depends(get_bank_statement_repo),
) -> ReviewService:
    return ReviewService(
        review_repo, invoice_repo, bank_txn_repo, audit_repo, statement_repo
    )


async def get_review_controller(
    review_service: ReviewService = Depends(get_review_service),
) -> ReviewController:
    return ReviewController(review_service)
