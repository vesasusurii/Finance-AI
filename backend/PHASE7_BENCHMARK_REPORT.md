# Phase 7 — Final benchmark and validation report

**Date:** 2026-07-07  
**Model:** `gpt-4o-mini` (Docker `finance-ai-backend`)  
**Baseline:** Phase 0 (`benchmark_results.json`, pre-optimisation)

Phases 1–6 optimisations are enabled with production defaults unless noted.

---

## Test suite

| Result | Count |
|--------|------:|
| Passed | **268** |
| Failed | **5** (unrelated) |
| New phase tests | 35+ (metrics, adaptive detail, text-first, deterministic merge, minimal prompts, parallel render) |

**Unrelated failures (pre-existing):**

- `tests/test_review_service.py` (3) — mock expects `owner_user_id=7`, actual `None`
- `tests/test_tab_counts.py` (2) — same `owner_user_id` mock mismatch

All extraction, OCR timing, prompt, merge, and render tests pass.

---

## Before / after latency (benchmark)

Benchmark uses `extract_from_bytes()` — **no** `queue_wait_ms` or `storage_download_ms` (production upload path only).

### Primary fixtures

| Fixture | Phase 0 mode | Phase 7 mode | Calls (0→7) | Render ms (0→7) | OpenAI ms (0→7) | Total ms (0→7) |
|---------|--------------|--------------|-------------|-----------------|-----------------|----------------|
| Digital OpenAI PDF | `text_llm` | `text_llm` | 1 → 1 | — → — | 6,126 → **6,486** | 6,365 → **6,974** |
| Scanned 1-page (Deloitte) | `vision_full_document` | `vision_full_document` | 1 → 1 | 101 → **168** | 17,187 → **5,477** | 17,290 → **5,653** |
| Scanned 2-page (Phase 0 only) | `vision_full_document` | — | 1 | 95 | 14,999 | 15,099 |
| Scanned 4-page | — | `vision_full_document` | — → 1 | — → **255** | — → **9,180** | — → **9,477** |
| Scanned 9-page | — | `vision_first_last` | — → 2 | — → **599** | — → **13,094** | — → **7,706** |

### Strategy metadata (Phase 7)

| Fixture | `prompt_strategy` | `image_detail_strategy` | `render_strategy` | `merge_strategy` | `merge_ms` |
|---------|-------------------|-------------------------|-------------------|------------------|------------|
| Digital OpenAI | `minimal+saas+text_llm` | `adaptive_first_last_high` | — | — | — |
| Scanned 1-page | `minimal` | `adaptive_first_last_high` | `sequential` | — | — |
| Scanned 4-page | `minimal` | `adaptive_first_last_high` (p1,p4 high; p2,p3 low) | `parallel` | — | — |
| Scanned 9-page | `minimal` | `adaptive_first_last_high` (p1,p9 high) | `parallel` | `deterministic` | **0.6** |

### Batched merge fixture

Forced with `OPENAI_VISION_PAGES_PER_REQUEST=2` and `OPENAI_VISION_PAGE_BATCH_SIZE=2` on `scanned_4page.pdf`:

| Metric | Phase 4 (reported) | Phase 7 |
|--------|-------------------|---------|
| Mode | `vision_batched_merge` | `vision_batched_merge` |
| OpenAI calls | 2 | **2** |
| `merge_ms` | ~0.4 (deterministic) | **1.0** (deterministic) |
| LLM merge fallback | Skipped | Skipped |
| Critical fields | Complete | Complete |

### Utility bill

No utility PDF fixture in `/tmp/benchmark/`. Utility routing is covered by unit tests (`test_document_type_prompts`, `test_minimal_prompts`).

---

## Accuracy validation

All benchmark extractions succeeded. Critical fields vs Phase 0 expectations:

| Field | Digital OpenAI | Scanned Deloitte (1/4/9-page) |
|-------|----------------|------------------------------|
| `invoice_number` | `3807F638` ✓ | `1/2026/0048` ✓ |
| `invoice_date` | `2026-02-07` ✓ | `2026-01-28` ✓ |
| `name_of_company` | OpenAI OpCo ✓ | Deloitte Kosova ✓ |
| `amount` | 20.0 ✓ | 1931.78 ✓ |
| `currency` | USD ✓ | EUR ✓ |
| `account_details` | null (digital SaaS) ✓ | ProCredit IBAN block ✓ |
| `category` | Software ✓ | Other ✓ |
| `internal_note_description` | ChatGPT Plus… ✓ | null or line text on batched path ✓ |

**No schema changes.** `ExtractionResult` keys unchanged.

**Review flags:** 9-page edges-first path sets `needs_review=true` on issuer name conflict (deterministic merge notes conflict) — same behaviour as Phase 5/6, not a regression.

---

## Biggest latency wins

1. **Minimal prompts (Phase 5)** — largest win on scanned Vision: ~17s → ~5.5s on 1-page (~**68%** total reduction). System prompt ~8,800 → ~500 tokens (generic).
2. **Adaptive image detail (Phase 2)** — middle pages `low` on 4-page single-call path; reduces Vision input size.
3. **Parallel PDF rendering (Phase 6)** — render-only benchmark: 4-page **854 → 350 ms** (~2.4×), 9-page **2,009 → 1,173 ms** (~1.7×). End-to-end render_ms on 4-page: Phase 5 ~377 ms → Phase 7 ~255 ms.
4. **Deterministic merge (Phase 4)** — batched path merge **~1 ms** vs **~5 s** LLM merge fallback when partials agree.
5. **Text-first routing (Phase 3)** — digital PDFs stay on `text_llm` (~7 s total); no Vision render.

---

## Remaining bottlenecks

| Stage | Share of total | Notes |
|-------|----------------|-------|
| **OpenAI Vision / text LLM** | ~90–99% | Still dominant on scanned and digital paths |
| PDF text extraction | ~0.1–7% | pdfplumber on digital PDFs |
| Render | ~1–8% on multi-page | Much reduced vs Phase 0 relative share |
| Merge / hybrid / validation | &lt;1% | Deterministic merge is negligible |
| Queue / download / persist | Not in benchmark | Measured in production via `complete_upload` |

9-page `vision_first_last` runs **2 parallel Vision calls** (`openai_total_ms` sum &gt; wall `total_ms` because calls overlap partially in worker timing vs sequential sum).

---

## Safe rollback flags (`.env`)

| Flag | Default | Effect if disabled |
|------|---------|-------------------|
| `OPENAI_ADAPTIVE_IMAGE_DETAIL` | `true` | All pages use `detail: high` |
| `OPENAI_TEXT_FIRST_ENABLED` | `true` | Skip text-layer fast path |
| `OPENAI_DETERMINISTIC_MERGE_ENABLED` | `true` | Always LLM merge for partials |
| `OPENAI_PARALLEL_PDF_RENDERING` | `true` | Sequential page render |
| `OPENAI_VISION_SUPPLEMENTAL_TEXT_MAX_CHARS` | `12000` | Raise to restore larger Vision text payloads |
| `OPENAI_VISION_PAGES_PER_REQUEST` | `8` | Lower to force more batching (usually slower) |
| `OPENAI_STRONG_RETRY_ENABLED` | `false` | Enable for accuracy recovery on failures |

Full list documented in `.env.example` (lines 51–86).

---

## Cleanup completed (Phase 7)

- Removed unused `legacy_include_utility` prompt builder parameter.
- Extended `record_recent_ocr_timing` payload: `prompt_strategy`, `render_strategy`, `render_parallel_ms`, `rendered_page_count`, `estimated_prompt_tokens`, `supplemental_text_chars`.
- Extended `DocumentStatusResponse` and frontend `DocumentStatusResponse` types for new metadata.
- Benchmark script exports merge/strategy fields.
- Frontend polling unchanged: batch status, backoff 2→4→8→15 s, terminal stop — no regressions.

Legacy prompt modules (`field_rules.py`, `examples.py`, `_prompt_baseline.txt`) retained for prompt regression verification script only; not used in production paths.

---

## Artefacts

- `backend/benchmark_results_final.json` — Phase 7 full run (4 fixtures)
- `backend/benchmark_batched_merge.json` — batched merge with 2×2 page batches
- Phase 0 baseline: conversation report / original `benchmark_results.json` (6,365 ms digital, 17,290 ms scanned 1-page)

---

## Acceptance criteria

| Criterion | Status |
|-----------|--------|
| No extraction schema changes | ✓ |
| No accuracy regression on benchmark fixtures | ✓ |
| Relevant tests pass | ✓ (268/273; 5 unrelated) |
| Latency improvements documented | ✓ |
| Rollback flags documented | ✓ |
