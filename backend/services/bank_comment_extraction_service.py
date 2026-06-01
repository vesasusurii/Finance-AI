"""
Bank comment LLM extraction service (doc 9, hybrid tier 2).

This sits behind the regex extractor in `utils/invoice_number_parser.py`.
When `needs_llm_fallback(comment, regex_candidates)` returns True, the
matching service hands the comment(s) to this service to disambiguate.

Design:
  - Async. Uses the same `AsyncOpenAI` client wired into app state.
  - Batched. One API call covers up to `BANK_COMMENT_LLM_BATCH_SIZE`
    comments (default 25) — cuts both latency and cost dramatically on
    statements with many ambiguous rows.
  - Cheap. Default model is `gpt-4o-mini`, with `temperature=0` and a strict
    JSON response format so output is deterministic across reconciliation
    runs.
  - Defensive. Any output the model emits is fed through the same
    `normalize_invoice_number` + `is_tax_or_client_id` filters as the regex
    path, so the DB lookup key format matches what the OCR side stored.
  - Optional. If `OPENAI_API_KEY` is missing or `BANK_COMMENT_USE_LLM=false`,
    the dependency-injection layer returns `None` and the matching service
    falls back to regex-only behaviour.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Iterable

from openai import APIConnectionError, APIStatusError, AsyncOpenAI, RateLimitError

from core.debug_logger import debug_trace, get_logger, log_typed_fields
from utils.normalization import is_tax_or_client_id, normalize_invoice_number
from utils.openai_chat import chat_completion_kwargs

_LLM_MAX_OUTPUT_TOKENS = 4096

logger = get_logger(__name__)


SYSTEM_PROMPT = """You extract supplier invoice / order reference numbers from bank transfer comments.

WHAT IS an invoice number:
- A short alphanumeric token that uniquely identifies a supplier invoice.
- Usually anchored by keywords: "Fatura", "Fat.", "Fature", "Inv", "Invoice",
  "Pagesa per fat.", "Pagese per fat.", "Payment for invoice".
- Examples of REAL invoice numbers:
    "26-0103"          (NLB-style year-sequence)
    "FDP25-00114712"   (alphanumeric prefix + dash + numbers)
    "1/2026/0048"      (slash-serial)
    "26063"            (bare numeric anchored by 'Invoice')

WHAT IS NOT an invoice number (NEVER return these):
- IBANs — start with 2 country letters + 2 check digits + alphanumerics
    e.g. MK07210701001870650, DE86270325000000013671, XK051234567890123456
- Bank account numbers — long pure-digit strings (>= 13 digits)
    e.g. 118900228600017, 1110343587000119
- Card approval / authorisation codes — after "APROVAL:", "AUTH:", "TERM:",
  "RRN:", or "REF:" with a random short token (e.g. "VCQVBGS0")
- Dates in any format — 11/02/2026, 2026-02-11, 11.02.2026, 20260211
- Tax IDs starting with 811 or 330 (Albanian fiscal IDs)
- Counterparty names, addresses, company registrations, phone numbers
- Currency codes, amounts

RULES:
- If the comment is a card payment, ATM withdrawal, salary transfer, bank fee,
  or any transaction with no supplier invoice reference, return an empty list.
- The same invoice may be repeated multiple times in one comment — return it
  ONCE. Do not duplicate.
- Return the invoice number AS WRITTEN in the comment (preserve dashes and
  slashes). Normalisation happens downstream.

OUTPUT FORMAT (strict JSON only, no prose):
{
  "results": [
    {"id": <int>, "invoice_numbers": [<string>, ...]},
    ...
  ]
}
"""


FEW_SHOT_EXAMPLE = {
    "results": [
        {"id": 1, "invoice_numbers": []},
        {"id": 2, "invoice_numbers": ["26-0103"]},
        {"id": 3, "invoice_numbers": ["FDP25-00114712", "FDP25-00133895"]},
        {"id": 4, "invoice_numbers": []},
    ]
}


FEW_SHOT_PROMPT = json.dumps(
    [
        {
            "id": 1,
            "comment": "APROVAL:503980; TERM:VCQVBGS0; HEYGEN TECHNOLOGY IN 11/02/2026 13:30:32 HEYGEN TECHNOLOGY INC. HEYGEN.COM US",
        },
        {
            "id": 2,
            "comment": "Inv 26-0103, NLB BANKA AD SKOPJE;MK07210701001870650;BOREK SOLUTIONS KOSOVO L.L.C.;Inv 26-0103",
        },
        {
            "id": 3,
            "comment": "Pagese per fat. FDP25-00114712 dhe FDP25-00133895, Uje Rugove SH.P.K.;118900228600017",
        },
        {
            "id": 4,
            "comment": "Commission Fee for Max Fichtner, BANKHAUS C.L. SEELIGER;DE86270325000000013671",
        },
    ],
    ensure_ascii=False,
)


@dataclass
class LLMExtractionResult:
    """Per-comment LLM result, normalised + filtered through the same rules
    as the regex path."""
    comment: str
    invoice_numbers: list[str] = field(default_factory=list)
    raw_numbers: list[str] = field(default_factory=list)


class BankCommentExtractionService:
    def __init__(
        self,
        openai_client: AsyncOpenAI,
        *,
        model: str,
        batch_size: int,
        timeout_seconds: int,
        max_retries: int,
    ) -> None:
        self._openai = openai_client
        self._model = model
        self._batch_size = max(1, batch_size)
        self._timeout_seconds = timeout_seconds
        self._max_retries = max(1, max_retries)

    # ─────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────

    @debug_trace
    async def extract_many(
        self, comments: list[str]
    ) -> list[LLMExtractionResult]:
        """
        Extract invoice numbers for `comments` in batches of `self._batch_size`.
        Returns one `LLMExtractionResult` per input comment, in order.
        """
        if not comments:
            return []

        results: list[LLMExtractionResult] = []
        for batch_start in range(0, len(comments), self._batch_size):
            batch = comments[batch_start : batch_start + self._batch_size]
            logger.debug(
                "LLM extract batch: %d comments (offset %d of %d total)",
                len(batch), batch_start, len(comments),
            )
            try:
                batch_results = await self._call_llm(batch)
            except Exception as exc:
                logger.exception(
                    "LLM extraction batch failed (offset=%d size=%d): %s",
                    batch_start, len(batch), exc,
                )
                # Fall back to empty results for the failed batch so the
                # caller can still proceed with regex-only candidates.
                batch_results = [
                    LLMExtractionResult(comment=c, invoice_numbers=[], raw_numbers=[])
                    for c in batch
                ]
            results.extend(batch_results)

        log_typed_fields(
            logger,
            "LLM extraction results",
            {
                "input_count": len(comments),
                "output_count": len(results),
                "with_invoices": sum(1 for r in results if r.invoice_numbers),
            },
        )
        return results

    # ─────────────────────────────────────────────────────────────────────
    # Internals
    # ─────────────────────────────────────────────────────────────────────

    @debug_trace
    async def _call_llm(self, batch: list[str]) -> list[LLMExtractionResult]:
        payload = [
            {"id": idx + 1, "comment": comment}
            for idx, comment in enumerate(batch)
        ]
        user_message = (
            "Extract invoice numbers from these bank transfer comments. "
            "Apply the rules from the system message strictly.\n\n"
            f"Example input:\n{FEW_SHOT_PROMPT}\n\n"
            f"Example output:\n{json.dumps(FEW_SHOT_EXAMPLE, ensure_ascii=False)}\n\n"
            "Now process these comments and return the same JSON shape:\n"
            f"{json.dumps(payload, ensure_ascii=False)}"
        )

        response = await self._chat_completion(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
        )
        raw_content = response.choices[0].message.content or "{}"
        logger.debug(
            "LLM raw response: %d chars (%s)",
            len(raw_content), type(raw_content).__name__,
        )

        return _parse_llm_response(raw_content, batch)

    @debug_trace
    async def _chat_completion(self, *, messages: list):
        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                return await self._openai.chat.completions.create(
                    model=self._model,
                    timeout=float(self._timeout_seconds),
                    messages=messages,
                    **chat_completion_kwargs(
                        self._model,
                        max_output_tokens=_LLM_MAX_OUTPUT_TOKENS,
                        temperature=0,
                        response_format={"type": "json_object"},
                    ),
                )
            except RateLimitError as exc:
                last_exc = exc
                logger.warning(
                    "LLM rate limited on attempt %d/%d", attempt + 1, self._max_retries
                )
            except APIConnectionError as exc:
                last_exc = exc
                logger.warning(
                    "LLM connection error on attempt %d/%d: %s",
                    attempt + 1, self._max_retries, exc,
                )
            except APIStatusError as exc:
                last_exc = exc
                if exc.status_code and exc.status_code >= 500:
                    continue
                raise
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("LLM call failed with no captured exception")


# ─────────────────────────────────────────────────────────────────────────────
# Response parsing
# ─────────────────────────────────────────────────────────────────────────────


def _parse_llm_response(
    raw: str, batch: list[str]
) -> list[LLMExtractionResult]:
    """Decode the JSON object, validate shape, normalise invoice numbers."""
    results: list[LLMExtractionResult] = [
        LLMExtractionResult(comment=c, invoice_numbers=[], raw_numbers=[])
        for c in batch
    ]

    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        cleaned = "\n".join(
            line for line in lines if not line.strip().startswith("```")
        ).strip()

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.warning("LLM returned non-JSON, ignoring batch: %s", exc)
        return results

    items = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        logger.warning(
            "LLM response missing 'results' list, ignoring batch (got %r)",
            type(payload).__name__,
        )
        return results

    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            idx = int(item.get("id"))
        except (TypeError, ValueError):
            continue
        if not 1 <= idx <= len(results):
            continue
        raw_numbers = item.get("invoice_numbers") or []
        if not isinstance(raw_numbers, list):
            continue

        cleaned_raw: list[str] = []
        normalised: list[str] = []
        for token in raw_numbers:
            if not isinstance(token, str):
                continue
            stripped = token.strip()
            if not stripped:
                continue
            cleaned_raw.append(stripped)
            norm = normalize_invoice_number(stripped)
            if not norm or is_tax_or_client_id(norm):
                continue
            if norm not in normalised:
                normalised.append(norm)

        results[idx - 1].raw_numbers = cleaned_raw
        results[idx - 1].invoice_numbers = normalised

    return results


def merge_candidates(
    regex_candidates: list[str], llm_candidates: Iterable[str]
) -> list[str]:
    """Union regex + LLM candidates, preserving regex order first."""
    merged = list(regex_candidates)
    for candidate in llm_candidates:
        if candidate and candidate not in merged:
            merged.append(candidate)
    return merged


__all__ = [
    "BankCommentExtractionService",
    "LLMExtractionResult",
    "merge_candidates",
]
