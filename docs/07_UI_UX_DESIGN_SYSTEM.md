# 07 — Formal UI/UX Specification (Enterprise SaaS, No Gradient Overuse)

## 1. Design principles

The interface should look like a modern paid enterprise learning product, not a demo chatbot. **Typography-driven hierarchy; generous whitespace; neutral backgrounds; a single restrained accent; nearly no gradients.** Inspiration: editorial precision, polished engineering tools, accessible dashboards. Do **not** copy any company's proprietary screens or branding. No neon gradients, blob backgrounds, glassmorphism, flashy AI mascots, excessive animations, rounded-everything or giant shadows.

## 2. Visual tokens

Use CSS variables compatible with shadcn/ui and Tailwind; define light and dark themes. Suggested **light theme**:

| Token | Hex | Usage |
| --- | --- | --- |
| `--background` | `#F8FAFC` | app canvas |
| `--surface` | `#FFFFFF` | panels and cards |
| `--surface-muted` | `#F1F5F9` | inset/hover |
| `--foreground` | `#0F172A` | primary body |
| `--muted-foreground` | `#64748B` | helper content |
| `--border` | `#E2E8F0` | card outlines and separators |
| `--primary` | `#1D4ED8` | action links/buttons |
| `--primary-hover` | `#1E40AF` | hover |
| `--success` | `#15803D` | ready/succeeded |
| `--warning` | `#B45309` | awaiting captions/partial |
| `--danger` | `#B91C1C` | failed/unauthorized |

Dark: `#0B1220` canvas, `#111C2D` surface, `#E5E7EB` ink, `#334155` borders, `#60A5FA` accent. Contrast >=4.5:1 for ordinary text and visible focus rings. Build semantic tokens, not arbitrary per-screen hex values.

Typography: `Inter` or `Geist` (system fallback) for UI; optional `Source Serif 4` **only** for lesson reading longform if desired. Page title 28–32px / 600, section title 18–22px / 600, body 14–16px / 400, helper 12–13px. Max text line width ~72ch. Standard border radius 8px (cards), 6px (controls), 12px (major panels). Shadows minimal. Vertical rhythm 8px grid; 24–32px layout gutter. Transitions 150–200ms with reduced-motion support.

## 3. Information architecture

Primary sidebar (desktop):
- Home / Dashboard
- My Library
- Playlists
- Videos
- Recent Learning
- Settings

Secondary content navigation: `Overview`, `Chapters`, `Summary`, `Ask AI`, `Transcript`, `Study Notes`. Do not show tabs that have no source data; show proper disabled/empty explanations.

## 4. Main screens and requirements

### Home / dashboard

Top row: title “Your learning workspace”, subtle description, primary “Add source” button. KPI row: videos ready, playlists, processing count, pending transcripts. Main cards: continue learning, recently imported, jobs needing attention. No useless charts.

### Add source

Single focused form with URL input and clear selector `Video / Playlist (automatic detection)`. Show metadata preview and real permission/coverage constraints. Three source methods: `Upload permitted subtitles`, `Paste permitted transcript`, `Owner-authorized captions (future / only if configured)`. Distinct buttons; upload attestation checkbox required. Do not imply the URL alone always yields knowledge.

### Library

Grid/list toggle; cards present title, source creator, item count/length, honest ready status and coverage. Filter status: Ready, Needs Transcript, Processing, Failed. Search within titles as first version. Context menu for delete/retry with confirmation.

### Playlist detail

Header: playlist title, channel if available, progress bar with exact `n of m ready`; row of filters. Left/main: ordered video lessons, duration and source availability. Right/secondary: playlist themes, summary and explicit “based on n/m videos” caveat. Missing videos never get invented chapter descriptions.

### Video lesson reader

Desktop 12-column layout: content/player/notes occupies ~8 columns; contextual outline/chat ~4 columns. At widths <1024, collapse the secondary panel to tabs/drawer. Top: title, channel, status, source quality badge. Embed official YouTube player in responsive 16:9 area when embeddable; if unavailable show graceful placeholder. Below: chapters with timecodes only where verified, summary, key ideas, source evidence snippets. Provide “Explain simply”, “Technical explanation”, “Copy notes” and “Ask about this” actions.

### AI tutor/chat

A clearly bounded section anchored to video/playlist. User bubble low visual weight; assistant response uses concise typography, citations as clickable chips/links, expandable “Supporting moments” drawer. Before first answer show starter queries derived from **available** evidence; disable questions when transcript absent. Streaming optional; no fake typing delays or simulated AI answers. Show response mode selector, and distinguish `source-backed` from `AI illustration`.

### Settings

Cards: text provider (OpenAI/Gemini/DeepSeek), chosen allowlisted model, embeddings provider/profile **read-only without reindex**, API key health (configured/unconfigured only), usage and limits, privacy/deletion. Show no full API keys and no frontend key input in MVP.

## 5. Components

Use shadcn/ui primitives (Button, Input, Card, Badge, Alert, Dialog, Tabs, Skeleton, Toast, DropdownMenu, Table, Progress). Compose domain components: `SourceUrlInput`, `TranscriptImportDialog`, `SourceStatusBadge`, `PlaylistCoverage`, `VideoLessonRow`, `ChapterTimeline`, `EvidenceCitation`, `SummaryPanel`, `ChatComposer`, `ProviderStatus`, `JobProgress`. Centralize status-to-label mapping, role-based layout, dark mode, toasts and errors.

No ornamental, inert buttons: every action must work or be visibly disabled with a reason. Use stable empty/error/skeleton states. Do not hide missing transcript warnings behind green 'AI analyzed' banners.

## 6. Responsive layouts

- >=1280px: 260px sidebar, content max width 1440px, secondary right panel 320–380px.
- 768–1279px: collapsible sidebar and stacked content, readable text widths.
- <768px: top bar, slide-out navigation; single-column detail; player 16:9; chat composer sticky only if it doesn't obscure content.
- Touch targets >=44px in dense mobile controls; keyboard navigation and screen-reader labels required.

## 7. States and copy

Status mapping:
- `needs_transcript` -> “Transcript needed” (amber); action “Add transcript”.
- `queued`/processing -> “Processing” (neutral) with stage and optional percent.
- `ready` -> “Ready to study” (green, not giant banner).
- `failed_retryable` -> “Processing interrupted” with retry.
- `not_authorized` -> “Permission required”.
- `unavailable` -> “Video unavailable”.
- `playlist partial` -> “Summary covers 9 of 12 videos”.

Avoid unsupported marketing statements like “Understands any YouTube video instantly”. Good alternative: “Turn supported video transcripts into lessons, summaries and cited answers.”

## 8. Accessibility and design QA

Semantic landmarks, headings in order, labeled inputs, form errors linked with aria-describedby, focus indicators, dialogs focus-trapped, tooltips not required to understand a status, prefers-reduced-motion honored, 200% zoom, keyboard-only main flows, WCAG AA contrast. Run axe (or equivalent) and Playwright screenshots at desktop, tablet, mobile in light and dark. Do not add Playwright snapshot baselines until UI settles; fix broken responsive state before pixel polish.

## 9. Ready-to-review UX acceptance checklist

- Visual system is consistent across all main screens.
- No large gradients anywhere; no arbitrary random colors or gratuitous animations.
- All required states have empty/loading/error/success views.
- Status/coverage accurate and understandable.
- Main flow achievable by keyboard on desktop and touch on mobile.
- Content-heavy screens remain readable, with line widths and whitespace appropriate.
- Unauthenticated/forbidden/API failure responses do not leak private content.
