# Borek Finance — Branding Guide

> **This document is the single source of truth for all visual design, copy tone, and UI behaviour in the Finance-AI project.**  
> Implementation lives in [`branding/theme.css`](./branding/theme.css). Read this file before building any UI, docs site, or marketing surface.

---

## Identity

| Field | Value |
|---|---|
| **Product name** | Borek Finance |
| **Repository** | Finance-AI |
| **Parent brand** | Borek Solutions Group |
| **Tagline** | Global Tech & AI Operations, German Precision. |
| **Audience** | Enterprise finance teams (B2B) |
| **Purpose** | Invoice and bank-statement matching — AI extracts, humans review |

---

## Non-negotiable rules

1. **Do not invent new colours.** Use only CSS variables from `branding/theme.css`.
2. **Canvas is always deep navy** (`--navy-700` / `#0D123F`). Primary text is white.
3. **Accent is coral-orange** (`--accent` / `#DB3714`) — eyebrows, links, primary CTAs, review states. Use sparingly.
4. **No emoji. No exclamation marks.** Calm, precise, enterprise tone.
5. **British spelling** — honour, centred, organisation.
6. **Headlines: sentence case**, weight 700, tracking `-0.01em`. Only the four Borek brand values are ALL CAPS.
7. **Eyebrows** — orange, UPPERCASE, weight 800, letter-spacing `0.12em` (class `.eyebrow`).
8. **Cards** — no drop shadows by default. Hairline borders only.
9. **Buttons** — pill shape (`border-radius: 9999px`). Ghost outline for nav; solid accent for primary actions.
10. **Motion** — `cubic-bezier(0.22, 1, 0.36, 1)`. 160 ms hover, 400 ms swap, 600 ms reveal. No bounce.

---

## Colour palette

### Raw tokens

| Token | Hex | Use |
|---|---|---|
| `--navy-900` | `#0A0D2A` | Deepest panels, gradient base |
| `--navy-800` | `#0C1036` | Footer, modals |
| `--navy-700` | `#0D123F` | **Page background (canonical)** |
| `--navy-600` | `#171C4D` | Cards, table hover |
| `--navy-500` | `#232A66` | Raised surfaces, selected rows |
| `--accent` | `#DB3714` | Eyebrows, links, primary CTAs |
| `--accent-600` | `#B82E0F` | Hover / pressed |
| `--accent-400` | `#EF845D` | Hero gradient mid-stop |
| `--teal-500` | `#02B0AC` | Photo duotone end-stop only |

### Semantic tokens (prefer these in components)

| Token | Maps to | Role |
|---|---|---|
| `--bg` | navy-700 | Page background |
| `--surface` | navy-600 | Cards, panels |
| `--surface-2` | navy-500 | Hover / selected |
| `--fg1` | white | Primary text |
| `--fg2` | white 70% | Body / secondary |
| `--fg3` | white 50% | Captions, table headers |
| `--hairline` | white 20% | Dividers |
| `--link` | accent | Inline links |

**Do not use green/red “success/error” colours** for match status. Use `.badge--matched`, `.badge--review`, `.badge--unmatched` from the theme.

---

## Typography

| Role | Size | Weight | Notes |
|---|---|---|---|
| Display | 96px | 800 | Hero only |
| H1 | 56px | 800 | Page titles |
| H2 | 44px | 700 | Section titles |
| H3 | 28px | 800 | Subsections |
| Eyebrow | 14px | 800 | UPPERCASE, accent colour |
| Body | 18px | 400 | `--fg2` on navy |
| Meta / table | 14px | — | Labels, nav links |
| Mono / tokens | 12px | — | Invoice numbers, IDs (`.tok`) |

**Fonts:** Mulish (sans — house font stand-in), Caveat (signature only). Load via Google Fonts in `theme.css`.

---

## Layout

- **Max content width:** 1280px (`.container`)
- **Desktop gutters:** 48px · **Mobile:** 24px
- **Section padding:** 120px top/bottom (`--space-8`)
- **Grid gutter:** 32px
- **8px spacing grid:** `--space-1` (4px) through `--space-8` (120px)

---

## Component classes (use these, do not reinvent)

| Pattern | Class |
|---|---|
| Page shell | `.container`, `.section` |
| Section intro | `.section-header` + `.eyebrow` + `h2` |
| Card | `.card`, `.card--flagged` |
| Primary CTA | `.btn.btn-accent` |
| Nav CTA | `.btn.btn-ghost` |
| Form field | `.field-label` + `.input` |
| Sticky nav | `.top-nav` |
| Footer | `.footer` |
| Hero band | `.hero-gradient` |
| Photo overlay | `.duotone-on-photo` |
| Data table | `.data-table` |
| File upload | `.upload-zone` |
| Match status | `.badge--matched` / `--review` / `--unmatched` |
| Toast | `.toast` |
| Modal | `.modal-bg` + `.modal` |

---

## Finance-app copy patterns

Use direct, factual language. Examples:

| Context | Preferred copy |
|---|---|
| Upload invoices | Upload purchase invoices |
| Upload bank file | Upload bank statement |
| Empty state | No invoices uploaded yet. |
| Review queue | Items awaiting finance review |
| Export | Export purchase invoices |
| Error (low confidence) | Extraction incomplete — please review manually. |

Avoid: “Awesome!”, “Oops!”, “🎉”, “Success!!!”, playful microcopy.

---

## Integration

### Plain HTML

```html
<link rel="stylesheet" href="branding/theme.css">
```

### React + Vite (planned stack)

```ts
// src/main.tsx
import '../branding/theme.css';
```

### CSS-in-JS / Tailwind (if added later)

Map design tokens from `:root` — never hard-code hex values in components. Example Tailwind extension:

```js
// tailwind.config — reference only; add when frontend exists
colors: {
  navy: { 700: '#0D123F', 600: '#171C4D', 500: '#232A66' },
  accent: { DEFAULT: '#DB3714', 600: '#B82E0F' },
}
```

---

## File map

```
Finance-AI/
├── BRANDING.md          ← you are here (rules + reference)
└── branding/
    └── theme.css        ← tokens, base styles, component classes
```

---

## For AI assistants

When implementing UI for this repository:

1. Open **`BRANDING.md`** and **`branding/theme.css`** first.
2. Import `branding/theme.css` in the app entry point.
3. Compose layouts with `.container`, `.card`, `.eyebrow`, `.btn-*` — do not duplicate styles.
4. Tables, uploads, and badges must use the finance-specific classes at the bottom of `theme.css`.
5. If a colour or font is not in `:root`, it does not belong in this project.
