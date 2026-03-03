# Monday.com Business Intelligence Agent
**Skylark Drones — Technical Assignment Submission**

---

## Overview

A single-file conversational BI agent that answers founder-level questions across Monday.com Work Orders and Deal Funnel boards, powered by Google Gemini 1.5 Flash.

**Every query triggers live Monday.com API calls — no caching.**

---

## Files

| File | Purpose |
|---|---|
| `app.py` | Complete Streamlit application (single file, ~1000 lines) |
| `Decision_Log.pdf` | 2-page architecture and trade-off log |
| `requirements.txt` | Python dependencies |
| `README.md` | This file |

---

## Quick Start

### 1. Install
```bash
pip install -r requirements.txt
```

### 2. Run
```bash
streamlit run app.py
```
Browser opens at `http://localhost:8501`

### 3. Configure (in sidebar)
| Field | Where to get it |
|---|---|
| **Gemini API Key** | [aistudio.google.com](https://aistudio.google.com) → Get API key (free) |
| **Monday.com Token** | Profile (top-right) → Developers → My Access Tokens |
| **Work Orders Board ID** | Open board → copy number from URL: `monday.com/boards/XXXXXXXXXX` |
| **Deal Funnel Board ID** | Same — for the Deal Funnel board |

> **No Monday.com account?** Upload the Excel files directly in the sidebar — the agent works identically.

---

## Monday.com Setup

### Import your Excel files as boards

1. Monday.com → **"+"** in left sidebar → **"Import data"** → **"Excel"**
2. Upload `Work_Order_Tracker_Data.xlsx` → name board: **Work Orders**
3. Upload `Deal_funnel_Data.xlsx` → name board: **Deal Funnel**
4. Copy each board's ID from the URL

### Get your API Token

Profile (top-right) → **Developers** → **My Access Tokens** → **Show** → Copy

---

## Architecture

```
User question
    │
    ▼
[Streamlit UI]
    │
    ├─► [Monday.com GraphQL API] ──► Fresh board data (every query)
    │       Step 1: boards.columns { id title }     ← col schema
    │       Step 2: items_page { items { id name    ← paginated items
    │                column_values { id text } } }
    │
    ├─► [Data Normalisation]
    │       norm_sector() ── canonical sector names
    │       norm_num()    ── handle masked/blank values
    │       dq_warnings() ── surface data quality issues
    │
    ├─► [Analytics Engine]
    │       analytics() ── sector aggregations, stage breakdown,
    │                      owner performance, AR, pipeline
    │
    ├─► [System Prompt Builder]
    │       build_prompt() ── inject live aggregations + 60/90 sample rows
    │                         + data quality caveats + instructions
    │
    └─► [Gemini 1.5-flash API]
            ask_gemini() ── with retry (3 attempts) + model fallback
            parse_trace() ── extract [TRACE: ...] from response
```

---

## Features

### ✅ Core Requirements
| Requirement | Implementation |
|---|---|
| Live Monday.com API | `fetch_board()` called inside `do_ask()` every query |
| No caching | `build_prompt()` and `analytics()` run fresh each time |
| Excel fallback | `st.file_uploader` → `load_excel()` → same pipeline |
| Null handling | `norm_num()`, `norm_date()`, `norm_sector()` |
| Format normalisation | `SECTOR_MAP` dict, regex numeric cleaning |
| Quality caveats | `dq_warnings()` shown in UI + injected into AI prompt |
| Founder-level queries | System prompt + natural language + follow-up context |
| Clarifying questions | AI instructed to ask ONE question when ambiguous |
| Multi-turn context | Full `gemini_history` sent every Gemini call |
| Cross-board BI | Both boards in every prompt; synthesis explicitly instructed |
| Visible tool traces | `[TRACE: ...]` in chat + **API Audit Log** tab |
| Conversational UI | Streamlit chat with history, quick queries, metrics bar |
| Error handling | Try/except everywhere; meaningful user-facing messages |
| Rate limit retry | 3 retries per model; cascades flash → flash-8b |

### ✅ UI Components
- **6 live metric cards** — Pipeline, WO value, Open deals, AR, Collected, API calls
- **Chat interface** — bubbles, traces, data quality banners per message
- **Quick Queries** — 9 preset founder questions in sidebar
- **API Audit Log tab** — every Monday.com call with timestamp, latency, KB
- **Refresh button** — re-fetch live data on demand

---

## Monday.com API Details

### Why two-step?
The `ColumnValue` type in Monday.com's GraphQL schema does NOT have a `title` field.
Only the `Column` type does. So:

```graphql
# Step 1: Get column title map  (boards.columns)
query { boards(ids: X) { columns { id title } } }

# Step 2: Get items  (column_values only has id + text)
query {
  boards(ids: X) {
    items_page(limit: 500, cursor: "...") {
      cursor
      items { id name column_values { id text } }
    }
  }
}
```

We build `{col_id → col_title}` from step 1 and apply it in step 2.

---

## Deployment (Hosted Prototype)

### Streamlit Cloud (free, recommended)
1. Push this folder to a GitHub repo
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect repo → select `app.py` → Deploy
4. Get a public URL in ~2 minutes

### Local
```bash
streamlit run app.py
# → http://localhost:8501
```

---

## Gemini API

- Model: `gemini-1.5-flash` (primary) → `gemini-1.5-flash-8b` (fallback)
- Free tier: 15 requests/min, 1,500 requests/day
- On 429: auto-retry with countdown timer shown in UI
- Get key: [aistudio.google.com](https://aistudio.google.com) → Get API key
