from schemas.invoice import ExtractionResult


class AIValidationService:
    def determine_review_status(self, result: ExtractionResult) -> str:
        if result.confidence_score >= 0.90 and not result.needs_review:
            return "pending"
        return "needs_review"

    def validate_required_fields(self, result: ExtractionResult) -> list[str]:
        missing: list[str] = []
        if not result.invoice_number:
            missing.append("invoice_number")
        if result.amount is None:
            missing.append("amount")
        if not result.name_of_company:
            missing.append("name_of_company")
        if not result.invoice_date:
            missing.append("invoice_date")
        return missing
