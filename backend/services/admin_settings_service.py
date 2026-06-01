from config import settings
from schemas.admin import SettingItem, SettingsResponse


def _yes_no(value: bool) -> str:
    return "Yes" if value else "No"


def _configured(value: str) -> str:
    return "Configured" if value.strip() else "Not configured"


class AdminSettingsService:
    def get_settings(self) -> SettingsResponse:
        items = [
            SettingItem(
                key="environment",
                label="Environment",
                value=settings.environment,
                group="General",
            ),
            SettingItem(
                key="log_level",
                label="Log level",
                value=settings.log_level,
                group="General",
            ),
            SettingItem(
                key="debug",
                label="Debug logging",
                value=_yes_no(settings.debug),
                group="General",
            ),
            SettingItem(
                key="storage_backend",
                label="Storage backend",
                value=settings.storage_backend,
                group="Storage",
            ),
            SettingItem(
                key="storage_path",
                label="Local storage path",
                value=settings.storage_path,
                group="Storage",
            ),
            SettingItem(
                key="supabase_bucket",
                label="Supabase bucket",
                value=settings.supabase_storage_bucket,
                group="Storage",
            ),
            SettingItem(
                key="supabase_url",
                label="Supabase URL",
                value=_configured(settings.supabase_url),
                group="Storage",
            ),
            SettingItem(
                key="openai",
                label="OpenAI API",
                value=_configured(settings.openai_api_key),
                group="AI extraction",
            ),
            SettingItem(
                key="openai_model",
                label="OpenAI model",
                value=settings.openai_model,
                group="AI extraction",
            ),
            SettingItem(
                key="openai_model_strong",
                label="OpenAI strong model",
                value=settings.openai_model_strong,
                group="AI extraction",
            ),
            SettingItem(
                key="bank_comment_llm",
                label="Bank comment LLM fallback",
                value=_yes_no(settings.bank_comment_use_llm),
                group="AI extraction",
            ),
            SettingItem(
                key="bank_comment_llm_model",
                label="Bank comment LLM model",
                value=settings.bank_comment_llm_model,
                group="Matching",
            ),
            SettingItem(
                key="batch_amount_matching",
                label="Batch amount matching",
                value=_yes_no(settings.batch_amount_matching_enabled),
                group="Matching",
            ),
            SettingItem(
                key="match_amount_tolerance",
                label="Amount match tolerance (EUR)",
                value=str(settings.match_amount_tolerance_eur),
                group="Matching",
            ),
            SettingItem(
                key="batch_amount_date_window",
                label="Batch amount date window (days)",
                value=str(settings.batch_amount_date_window_days),
                group="Matching",
            ),
            SettingItem(
                key="jwt_access_expire_minutes",
                label="Access token lifetime (minutes)",
                value=str(settings.jwt_access_expire_minutes),
                group="Authentication",
            ),
            SettingItem(
                key="jwt_refresh_expire_days",
                label="Refresh token lifetime (days)",
                value=str(settings.jwt_refresh_expire_days),
                group="Authentication",
            ),
            SettingItem(
                key="cookie_secure",
                label="Secure cookies",
                value=_yes_no(settings.cookie_secure),
                group="Authentication",
            ),
            SettingItem(
                key="smtp",
                label="SMTP email",
                value=_configured(settings.smtp_host),
                group="Email",
            ),
            SettingItem(
                key="smtp_from",
                label="From address",
                value=settings.smtp_from_email,
                group="Email",
            ),
        ]
        return SettingsResponse(items=items)
