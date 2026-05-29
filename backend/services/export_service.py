from datetime import date

from core.debug_logger import debug_trace
from core.invoice_access import invoice_owner_user_id
from repositories.report_repository import ReportRepository
from schemas.auth import UserContext
from schemas.report import PeriodReportResponse
from utils.period_ranges import VALID_PERIODS, period_range


class ExportService:
    def __init__(self, report_repo: ReportRepository) -> None:
        self._report_repo = report_repo

    @debug_trace
    async def period_report(
        self,
        period: str,
        anchor: date,
        user: UserContext,
    ) -> PeriodReportResponse:
        if period not in VALID_PERIODS:
            raise ValueError(
                f"Invalid period {period!r}. Use day, week, month, or year."
            )

        start, end, label = period_range(period, anchor)  # type: ignore[arg-type]
        owner = invoice_owner_user_id(user)

        invoice_stats = await self._report_repo.invoice_period_stats(
            start,
            end,
            owner_user_id=owner,
        )
        bank_stats = await self._report_repo.bank_period_stats(
            start,
            end,
            owner_user_id=owner,
        )
        by_category = await self._report_repo.category_breakdown(
            start,
            end,
            owner_user_id=owner,
        )

        return PeriodReportResponse(
            period=period,
            period_label=label,
            start_date=start,
            end_date=end,
            by_category=by_category,
            **invoice_stats,
            **bank_stats,
        )
