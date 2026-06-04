# Finance-AI Documentation

Canonical numbered docs (use these for implementation). Aligned with the original project specification (Sections 1–20).

| Doc | Topic | ODT sections |
|---|---|---|
| [2. Tech Stack.md](./2. Tech Stack.md) | Architecture, APIs, phases, frontend pages | 4, 9–11, 13, 17 |
| [3. Technical Workflow 1.md](./3. Technical Workflow 1.md) | End-to-end steps, confidence, review | 3, 7–8, 14, 19 |
| [6. Backend Architecture 1.md](./6. Backend Architecture 1.md) | Folder structure, layers, traced examples | 9, 11 |
| [7. DB Schema 1.md](./7. DB Schema 1.md) | PostgreSQL tables, indexes, Excel mapping | 12, 15 |
| [8. OCR-Technology.md](./8. OCR-Technology.md) | OpenAI primary, Google fallback, golden samples | 10 |
| [9. Matching-Normalization.md](./9. Matching-Normalization.md) | Comment parsing, normalization, matching | 5–7 |
| [10. Excel-File-Formats.md](./10. Excel-File-Formats.md) | PI export columns, bank import rows | 2, 15 |
| [11. Security & Compliance.md](./11. Security & Compliance.md) | Auth, RBAC, audit, AI DPAs, deployment | 16, 20 |

**Not yet separate docs** (covered inside numbered set or post-MVP):

| Topic | Where today | Future doc (optional) |
|---|---|---|
| Phase 5 monthly reports | [2. Tech Stack.md](./2. Tech Stack.md), [10. Excel-File-Formats.md](./10. Excel-File-Formats.md) §Phase 5 | `12. Reports.md` |
| E2E / CI testing | [8. OCR-Technology.md](./8. OCR-Technology.md), [9. Matching-Normalization.md](./9. Matching-Normalization.md) | `13. Testing.md` |
| Deployment / ops runbook | [11. Security & Compliance.md](./11. Security & Compliance.md) checklist | `14. Deployment.md` |

**Core rules (always):**

1. Invoices: upload **PDF/images** only — OCR stores data; Excel is **download** only.
2. Bank: upload **Excel** only — **no bank API**.
3. Matching: `Komenti / Comment` → invoice number → `paid at (Date)`; **`paid by` manual**.
4. Never guess when comment or AI confidence is weak — use **Needs Review**.

---

## Requirements compliance (audit)

| Requirement (spec) | Status | Where documented |
|---|---|---|
| Upload invoices PDF/image, not Excel | ✅ Met | 2, 3, 8, 10 |
| OCR → structured JSON → PostgreSQL | ✅ Met | 2, 3, 6, 7, 8 |
| Download Purchase Invoices Excel (12 columns, `Adress` spelling) | ✅ Met | 7, 10, 3 Step 7 |
| Upload bank statement Excel only | ✅ Met | 2, 3, 10, 11 |
| Parse `Komenti / Comment`, normalize, exact match | ✅ Met | 9, 3 Step 4 |
| Auto-fill **paid at (Date)** only from bank date | ✅ Met | 3, 9, 8 (OCR excludes paid fields) |
| **paid by** always manual | ✅ Met | All core docs |
| Confidence tiers 90 / 70 / &lt;70 | ✅ Met | 2, 3, 8 |
| Manual review queue + approve/reject | ✅ Met | 3 Step 6, 6, 7 |
| Security: no bank API, auth, RBAC, audit, secure files | ✅ Met | 11 |
| OpenAI primary, Google failover | ✅ Met | 8, 2 |
| MVP Phases 1–4 | ✅ Met | 2, 3, 6 |
| Phase 5 monthly reports | ⚠️ Stub only | 2, 10 §Phase 5 — metrics listed, format TBD |
| All APIs from spec §11 | ⚠️ Mostly met | 2 — added `GET /api/files/{id}`, `GET /api/review/tasks` |
| Frontend page-level acceptance criteria | ⚠️ Partial | 2 (page list only) |
| E2E / CI testing strategy | ⚠️ Partial | 8, 9 (eval scripts only) |
| Deployment / ops runbook | ⚠️ Partial | 11 (checklist only) |
| Intern task breakdown (spec §18) | ❌ Missing | Was in removed extended doc — add when team splits work |
| Finance pending decisions | 📋 Listed | `DOCS/FINANCE_PENDING_DECISIONS.md`; also 8, 9, 10 §12 |

**Verdict:** Documentation is **sufficient to start MVP implementation** (Phases 1–4). Gaps are post-MVP reporting, dedicated testing/UI specs, and Finance sign-off on pending decisions — not blockers for core invoice + bank matching flow.
