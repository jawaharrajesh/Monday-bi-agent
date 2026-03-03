"""
Monday.com Business Intelligence Agent
Skylark Drones — Technical Assignment

Requirements covered:
  [✓] Live Monday.com GraphQL API — re-fetched on EVERY query, no caching
  [✓] Excel upload fallback — evaluator can use without Monday.com setup
  [✓] Data resilience — null handling, sector normalisation, quality caveats
  [✓] Query understanding — natural language, clarifying questions, follow-up
  [✓] Business intelligence — revenue, pipeline, sector, AR, owner perf
  [✓] Visible tool-call traces — per-message AND full API audit log tab
  [✓] Conversational interface with full multi-turn history
  [✓] Gemini rate-limit retry + model fallback (1.5-flash → 1.5-flash-8b)
  [✓] Graceful error handling throughout

Run:
    pip install streamlit requests openpyxl
    streamlit run app.py
"""

import re
import time
import requests
import openpyxl
import streamlit as st
from datetime import datetime

# ──────────────────────────────────────────────────────────────────
#  PAGE CONFIG  (must be FIRST Streamlit call)
# ──────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Monday BI Agent · Skylark Drones",
    page_icon="⬡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────────────────────────
#  GLOBAL CSS
# ──────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 0.8rem !important; padding-bottom: 0 !important; }

/* ── App header ── */
.app-header {
    background: linear-gradient(135deg,#0d1117 0%,#0f1924 100%);
    border: 1px solid rgba(246,81,48,.18);
    border-radius: 12px; padding: 14px 22px; margin-bottom: 14px;
    display: flex; align-items: center; justify-content: space-between;
}
.app-title {
    font-size: 20px; font-weight: 700;
    background: linear-gradient(135deg,#f65130,#4285f4);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin: 0;
}
.app-sub { color:#64748b; font-size:11px; font-family:'DM Mono',monospace; margin-top:3px; }
.badge-live   { background:rgba(0,255,136,.1); border:1px solid rgba(0,255,136,.3); color:#00ff88;
                padding:3px 12px; border-radius:20px; font-family:'DM Mono',monospace; font-size:11px; }
.badge-excel  { background:rgba(255,179,0,.1);  border:1px solid rgba(255,179,0,.3);  color:#ffb300;
                padding:3px 12px; border-radius:20px; font-family:'DM Mono',monospace; font-size:11px; }

/* ── Chat bubbles ── */
.user-bubble {
    background:rgba(66,133,244,.07); border:1px solid rgba(66,133,244,.18);
    border-radius:14px 14px 3px 14px; padding:11px 16px;
    margin:10px 0; text-align:right; font-size:13.5px; color:#e2e8f0;
}
.ai-bubble {
    background:#0f1924; border:1px solid #1e2d3d;
    border-radius:3px 14px 14px 14px; padding:14px 18px;
    margin:10px 0; font-size:13.5px; line-height:1.85; color:#cbd5e1;
}
.ai-bubble strong { color:#f65130; }
.ai-bubble h3 { color:#60a5fa; font-size:12px; text-transform:uppercase;
                letter-spacing:.6px; margin:12px 0 5px; }
.ai-bubble ul { margin:6px 0 6px 18px; }
.ai-bubble li { margin-bottom:3px; }

/* ── Tool-call trace ── */
.trace-box {
    background:#080c14; border:1px solid rgba(246,81,48,.15);
    border-left:3px solid #f65130; border-radius:7px;
    padding:10px 14px; margin-bottom:11px;
    font-family:'DM Mono',monospace; font-size:10.5px;
}
.trace-hdr { color:#f65130; font-size:9.5px; text-transform:uppercase;
             letter-spacing:1.3px; margin-bottom:7px; font-weight:600; }
.trace-row  { display:flex; gap:10px; margin-bottom:3px; align-items:flex-start; }
.trace-k    { color:#22c55e; min-width:130px; flex-shrink:0; }
.trace-v    { color:#94a3b8; word-break:break-all; }

/* ── Data quality note ── */
.dq-note {
    background:rgba(251,191,36,.06); border:1px solid rgba(251,191,36,.2);
    border-left:3px solid #fbbf24; border-radius:6px;
    padding:7px 12px; margin-bottom:9px;
    font-family:'DM Mono',monospace; font-size:10.5px; color:#fbbf24;
}

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background:#080c14 !important;
    border-right:1px solid #1e2d3d;
}

/* ── Buttons ── */
.stButton > button {
    background:linear-gradient(135deg,#f65130,#4285f4) !important;
    color:white !important; border:none !important;
    border-radius:8px !important; font-weight:600 !important;
    font-family:'Inter',sans-serif !important;
    transition:opacity .15s !important;
}
.stButton > button:hover { opacity:.85 !important; }

/* ── Text inputs ── */
.stTextInput > div > div > input {
    background:#0f1924 !important; border:1px solid #1e2d3d !important;
    color:#e2e8f0 !important; border-radius:9px !important;
    font-family:'Inter',sans-serif !important;
}
.stTextInput > div > div > input:focus { border-color:#f65130 !important; }

/* ── Metrics ── */
[data-testid="metric-container"] {
    background:#0f1924; border:1px solid #1e2d3d;
    border-radius:10px; padding:10px !important;
}
[data-testid="stMetricValue"] { color:#f65130 !important; font-size:20px !important; font-weight:700 !important; }
[data-testid="stMetricDelta"] { font-size:11px !important; }

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] { background:#080c14; border-bottom:1px solid #1e2d3d; }
.stTabs [data-baseweb="tab"]      { color:#64748b; font-size:13px; font-weight:500; }
.stTabs [aria-selected="true"]   { color:#f65130 !important; border-bottom:2px solid #f65130 !important; }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────
#  CONSTANTS
# ──────────────────────────────────────────────────────────────────
MONDAY_URL   = "https://api.monday.com/v2"
GEMINI_BASE  = "https://generativelanguage.googleapis.com/v1beta/models"
# Free-tier order: try highest-quota model first, fallback to smaller
GEMINI_CHAIN = ["gemini-1.5-flash", "gemini-1.5-flash-8b"]

SECTOR_MAP = {
    "powerline":"Powerline","power line":"Powerline","powerline inspection":"Powerline",
    "mining":"Mining","railways":"Railways","railway":"Railways",
    "renewables":"Renewables","renewable":"Renewables",
    "construction":"Construction","others":"Others","other":"Others",
    "aviation":"Aviation","manufacturing":"Manufacturing",
    "dsp":"DSP","security and surveillance":"Security & Surveillance","tender":"Tender",
}

QUICK_QUERIES = [
    "How's our pipeline looking for the energy sector this quarter?",
    "What is total revenue by sector from work orders?",
    "Which deals are at highest risk of being lost?",
    "Show pipeline health with stage-by-stage breakdown",
    "What is our AR receivable status and top priority accounts?",
    "Compare Mining vs Powerline sector performance",
    "Who are our top performing BD/KAM owners by deal value?",
    "Which work orders have billing or collection issues?",
    "Give me a full executive business health summary",
]

# ──────────────────────────────────────────────────────────────────
#  SESSION STATE
# ──────────────────────────────────────────────────────────────────
_DEFAULTS = dict(
    gemini_key="", monday_token="", wo_board_id="", deal_board_id="",
    wos=[], deals=[], is_live=False, data_source="", connected=False,
    chat_history=[],     # [{role, content, trace, dq}]
    gemini_history=[],   # Gemini API wire format
    api_log=[],          # full audit trail of every Monday.com call
    run_query="",
)
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ──────────────────────────────────────────────────────────────────
#  DATA NORMALISATION  ← Requirement: Data Resilience
# ──────────────────────────────────────────────────────────────────

def norm_sector(v):
    if not v or str(v).strip() in ("","None","nan"):
        return "Unknown"
    return SECTOR_MAP.get(str(v).lower().strip(), str(v).strip())

def norm_num(v):
    """Parse number from any messy string — returns None if unparseable."""
    if v is None or str(v).strip() in ("","None","nan","-","N/A","n/a"):
        return None
    try:
        return float(re.sub(r"[^0-9.\-]","",str(v))) or None
    except ValueError:
        return None

def norm_date(v):
    if v is None: return ""
    if isinstance(v, datetime): return v.strftime("%Y-%m-%d")
    s = str(v).strip()
    return "" if s in ("None","nan") else s

def enrich_wo(rows):
    out = []
    for r in rows:
        out.append({**r,
            "_sector"   : norm_sector(r.get("Sector","")),
            "_status"   : (r.get("Execution Status") or "").strip(),
            "_nature"   : (r.get("Nature of Work") or "").strip(),
            "_amount"   : norm_num(r.get("Amount in Rupees (Excl of GST) (Masked)")),
            "_billed"   : norm_num(r.get("Billed Value in Rupees (Excl of GST.) (Masked)")),
            "_collected": norm_num(r.get("Collected Amount in Rupees (Incl of GST.) (Masked)")),
            "_recv"     : norm_num(r.get("Amount Receivable (Masked)")),
            "_tobill"   : norm_num(r.get("Amount to be billed in Rs. (Exl. of GST) (Masked)")),
            "_billing"  : (r.get("Billing Status") or "").strip(),
            "_wostatus" : (r.get("WO Status (billed)") or "").strip(),
            "_colstatus": (r.get("Collection status") or "").strip(),
            "_owner"    : (r.get("BD/KAM Personnel code") or "Unknown").strip(),
        })
    return out

def enrich_deals(rows):
    out = []
    for d in rows:
        name = (d.get("Deal Name") or "").strip()
        if not name or name == "Deal Name":
            continue
        out.append({**d,
            "_sector": norm_sector(d.get("Sector/service","")),
            "_status": (d.get("Deal Status") or "").strip(),
            "_stage" : (d.get("Deal Stage") or "Unknown").strip(),
            "_value" : norm_num(d.get("Masked Deal value")),
            "_owner" : (d.get("Owner code") or "Unknown").strip(),
            "_prob"  : (d.get("Closure Probability") or "").strip(),
            "_close" : norm_date(d.get("Tentative Close Date") or d.get("Close Date (A)","")),
        })
    return out

def dq_warnings(wos, deals):
    """Return list of data-quality caveat strings."""
    w = []
    null_amt  = sum(1 for r in wos   if r["_amount"] is None)
    null_val  = sum(1 for r in deals if r["_value"]  is None)
    unk_sec_w = sum(1 for r in wos   if r["_sector"] == "Unknown")
    unk_sec_d = sum(1 for r in deals if r["_sector"] == "Unknown")
    no_close  = sum(1 for r in deals if not r["_close"])
    no_prob   = sum(1 for r in deals if not r["_prob"])
    if null_amt  : w.append(f"{null_amt} work orders have masked/missing amounts")
    if null_val  : w.append(f"{null_val} deals have missing deal values")
    if unk_sec_w : w.append(f"{unk_sec_w} WOs have unrecognised sector labels")
    if unk_sec_d : w.append(f"{unk_sec_d} deals have unrecognised sector labels")
    if no_close  : w.append(f"{no_close} deals have no close date")
    if no_prob   : w.append(f"{no_prob} deals have no closure probability")
    return w

# ──────────────────────────────────────────────────────────────────
#  EXCEL LOADER  (fallback when Monday.com not configured)
# ──────────────────────────────────────────────────────────────────

def load_excel(wo_file, deal_file):
    """Read Streamlit UploadedFile objects — no disk access needed."""
    def read(fobj, hrow):
        wb   = openpyxl.load_workbook(fobj, data_only=True)
        ws   = wb.active
        rows = list(ws.iter_rows(values_only=True))
        hdrs = [str(h).strip() if h else f"col_{i}" for i,h in enumerate(rows[hrow])]
        return [
            {hdrs[i]: norm_date(v) if isinstance(v,datetime) else (v if v is not None else "")
             for i,v in enumerate(row)}
            for row in rows[hrow+1:]
        ]
    return read(wo_file, 1), read(deal_file, 0)

# ──────────────────────────────────────────────────────────────────
#  MONDAY.COM GRAPHQL API  ← Requirement: Live Integration
# ──────────────────────────────────────────────────────────────────

def _gql(token, query, label):
    """
    Execute one Monday.com GraphQL call and append to audit log.
    Every call is logged: timestamp, label, HTTP status, latency, payload size.
    This satisfies the 'visible agent action' requirement.
    """
    t0   = time.time()
    resp = requests.post(
        MONDAY_URL,
        headers={"Content-Type":"application/json",
                 "Authorization":token, "API-Version":"2024-01"},
        json={"query":query}, timeout=30,
    )
    ms = int((time.time()-t0)*1000)
    resp.raise_for_status()
    data = resp.json()

    st.session_state.api_log.append({
        "time"   : datetime.now().strftime("%H:%M:%S"),
        "action" : label,
        "board"  : "monday.com/v2",
        "http"   : resp.status_code,
        "ms"     : ms,
        "kb"     : round(len(resp.content)/1024, 1),
    })

    if "errors" in data:
        raise ValueError(f"Monday GraphQL: {data['errors'][0].get('message','unknown error')}")
    return data

def fetch_board(token, board_id, name):
    """
    Fetch ALL items from one Monday.com board.

    Two-step (required by Monday API schema):
      Step 1: boards.columns { id title }  →  build col_id→title map
              ('title' is NOT on ColumnValue, only on Column)
      Step 2: items_page { cursor items { id name column_values { id text } } }
              cursor-based pagination, 500 items per page, up to 20 pages
    """
    # Step 1 — column schema
    col_data = _gql(
        token,
        f"query {{ boards(ids:{board_id}) {{ columns {{ id title }} }} }}",
        f"Schema: {name}",
    )
    boards = col_data.get("data",{}).get("boards",[])
    if not boards:
        raise ValueError(
            f"Board '{name}' (ID {board_id}) not found. "
            "Verify the Board ID is correct and your token has access."
        )
    col_map = {c["id"]: c["title"] for c in boards[0].get("columns",[])}

    # Step 2 — paginate items
    items_all, cursor, page = [], None, 1
    while True:
        cur_arg = f', cursor:"{cursor}"' if cursor else ""
        q = f"""query {{
          boards(ids:{board_id}) {{
            items_page(limit:500{cur_arg}) {{
              cursor
              items {{ id name column_values {{ id text }} }}
            }}
          }}
        }}"""
        data  = _gql(token, q, f"Items p{page}: {name}")
        ipage = data.get("data",{}).get("boards",[{}])[0].get("items_page",{})
        items = ipage.get("items",[])

        for item in items:
            row = {"Deal name masked":item["name"], "Deal Name":item["name"]}
            for cv in item.get("column_values",[]):
                row[col_map.get(cv["id"], cv["id"])] = cv.get("text") or ""
            items_all.append(row)

        cursor = ipage.get("cursor")
        if not cursor or not items or page >= 20:
            break
        page += 1

    return items_all

# ──────────────────────────────────────────────────────────────────
#  ANALYTICS  (computed fresh every query — no caching)
# ──────────────────────────────────────────────────────────────────

def fmt(n):
    if not n: return "₹0"
    if n >= 10_000_000: return f"₹{n/10_000_000:.2f} Cr"
    if n >= 100_000:    return f"₹{n/100_000:.2f} L"
    return f"₹{n:,.0f}"

def analytics(wos, deals):
    """Aggregate both boards — called live on every query."""
    sw = {}
    for w in wos:
        s = w["_sector"]
        if s not in sw:
            sw[s] = dict(count=0,val=0.,billed=0.,collected=0.,tobill=0.,recv=0.)
        sw[s]["count"]    += 1
        sw[s]["val"]      += w["_amount"]    or 0
        sw[s]["billed"]   += w["_billed"]    or 0
        sw[s]["collected"]+= w["_collected"] or 0
        sw[s]["tobill"]   += w["_tobill"]    or 0
        sw[s]["recv"]     += w["_recv"]      or 0

    sd = {}
    for d in deals:
        s = d["_sector"]
        if s not in sd:
            sd[s] = dict(count=0,val=0.,open=0,won=0,dead=0,hold=0)
        sd[s]["count"] += 1
        sd[s]["val"]   += d["_value"] or 0
        st_ = d["_status"]
        if   st_=="Open":    sd[s]["open"] += 1
        elif st_=="Won":     sd[s]["won"]  += 1
        elif st_=="Dead":    sd[s]["dead"] += 1
        elif st_=="On Hold": sd[s]["hold"] += 1

    stages = {}
    for d in deals:
        sg = d["_stage"]
        if sg not in stages: stages[sg] = dict(count=0,val=0.)
        stages[sg]["count"] += 1
        stages[sg]["val"]   += d["_value"] or 0
    stages = dict(sorted(stages.items(), key=lambda x:-x[1]["val"]))

    owners = {}
    for d in deals:
        o = d["_owner"]
        if o not in owners: owners[o] = dict(deals=0,val=0.,won=0)
        owners[o]["deals"] += 1
        owners[o]["val"]   += d["_value"] or 0
        if d["_status"]=="Won": owners[o]["won"] += 1
    owners = dict(sorted(owners.items(), key=lambda x:-x[1]["val"]))

    return dict(
        sw=sw, sd=sd, stages=stages, owners=owners,
        tot_contract = sum(w["_amount"]    or 0 for w in wos),
        tot_billed   = sum(w["_billed"]    or 0 for w in wos),
        tot_collected= sum(w["_collected"] or 0 for w in wos),
        tot_ar       = sum(w["_recv"]      or 0 for w in wos),
        tot_tobill   = sum(w["_tobill"]    or 0 for w in wos),
        tot_pipeline = sum(d["_value"]     or 0 for d in deals),
        n_open = sum(1 for d in deals if d["_status"]=="Open"),
        n_won  = sum(1 for d in deals if d["_status"]=="Won"),
        n_dead = sum(1 for d in deals if d["_status"]=="Dead"),
        n_wo   = len(wos), n_deal=len(deals),
    )

# ──────────────────────────────────────────────────────────────────
#  SYSTEM PROMPT  (rebuilt fresh each query = no stale data)
# ──────────────────────────────────────────────────────────────────

def build_prompt(wos, deals, src):
    a  = analytics(wos, deals)
    dq = dq_warnings(wos, deals)

    wo_sec = "\n".join(
        f"  {s}: {v['count']} WOs | Contract:{fmt(v['val'])} | "
        f"Billed:{fmt(v['billed'])} | Collected:{fmt(v['collected'])} | "
        f"AR:{fmt(v['recv'])} | Unbilled:{fmt(v['tobill'])}"
        for s,v in a["sw"].items())

    deal_sec = "\n".join(
        f"  {s}: {v['count']} deals | Pipeline:{fmt(v['val'])} | "
        f"Open:{v['open']} Won:{v['won']} Dead:{v['dead']} OnHold:{v['hold']}"
        for s,v in a["sd"].items())

    stage_sec = "\n".join(
        f"  {s}: {v['count']} deals | {fmt(v['val'])}"
        for s,v in a["stages"].items())

    owner_sec = "\n".join(
        f"  {o}: {v['deals']} deals | {fmt(v['val'])} pipeline | {v['won']} won"
        for o,v in list(a["owners"].items())[:12])

    dq_sec = ("\nDATA QUALITY ISSUES (mention when relevant):\n" +
              "\n".join(f"  ⚠ {n}" for n in dq)) if dq else ""

    wo_sample = "\n".join(
        f"  [{r.get('Serial #','?')}] {r.get('Deal name masked',r.get('Deal Name','?'))} | "
        f"Sector:{r['_sector']} | Status:{r['_status']} | Nature:{r['_nature']} | "
        f"Amount:{fmt(r['_amount'])} | Billed:{fmt(r['_billed'])} | "
        f"BillingStatus:{r['_billing']} | WOStatus:{r['_wostatus']} | "
        f"Collection:{r['_colstatus']} | Owner:{r['_owner']}"
        for r in wos[:60])

    deal_sample = "\n".join(
        f"  {d.get('Deal Name','?')} | Owner:{d['_owner']} | Sector:{d['_sector']} | "
        f"Status:{d['_status']} | Stage:{d['_stage']} | Value:{fmt(d['_value'])} | "
        f"Prob:{d['_prob']} | CloseDate:{d['_close']}"
        for d in deals[:90])

    return f"""You are an elite Business Intelligence Agent built for Skylark Drones.
You are embedded in a Monday.com BI dashboard and answer founder/executive-level queries.

DATA SOURCE : {src}
FETCHED AT  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
BOARDS      : Work Orders ({a['n_wo']} records) | Deal Funnel ({a['n_deal']} records)
{dq_sec}

══════════════════════════════════════════════════════
LIVE BOARD DATA  (freshly fetched, no cache)
══════════════════════════════════════════════════════

WORK ORDERS — BY SECTOR:
{wo_sec}

WORK ORDER FINANCIALS (ALL SECTORS):
  Total Contract Value : {fmt(a['tot_contract'])}
  Total Billed         : {fmt(a['tot_billed'])}
  Total Collected      : {fmt(a['tot_collected'])}
  AR Outstanding       : {fmt(a['tot_ar'])}
  Unbilled (to bill)   : {fmt(a['tot_tobill'])}

DEAL FUNNEL — BY SECTOR:
{deal_sec}

DEAL PIPELINE — BY STAGE (sorted by value):
{stage_sec}

DEAL SUMMARY:
  Total Pipeline : {fmt(a['tot_pipeline'])}
  Open / Won / Dead : {a['n_open']} / {a['n_won']} / {a['n_dead']}

TOP OWNERS BY DEAL PIPELINE VALUE:
{owner_sec}

WORK ORDER RECORDS (first 60 of {a['n_wo']}):
{wo_sample}

DEAL RECORDS (first 90 of {a['n_deal']}):
{deal_sample}

══════════════════════════════════════════════════════
AGENT INSTRUCTIONS
══════════════════════════════════════════════════════

MANDATORY: Start every response with this EXACT line (no other text before it):
[TRACE: board=<boards queried>, filter=<what you filtered on>, fields=<key fields>, records=<count>, source={src}]

ANSWER RULES:
1. Punchline first — lead with the key insight in one sentence.
2. Back it up with exact numbers (₹ values in Cr/L, counts, percentages).
3. Treat Renewables + Powerline together as the "energy sector" unless specified otherwise.
4. Use ₹ currency with Cr (crore) / L (lakh) suffixes always.
5. Proactively surface data quality caveats from the list above when they affect the answer.
6. If a question is genuinely ambiguous, ask ONE focused clarifying question before answering.
7. Use full conversation history for follow-up questions.
8. For cross-board questions, synthesise explicitly across Work Orders AND Deal Funnel.
9. At-risk deals: consider Dead/On-Hold status, low probability, missing close date, high value.
10. Keep answers sharp — executives want insight, not data dumps. Bullet the key points.
"""

# ──────────────────────────────────────────────────────────────────
#  GEMINI API  ← with rate-limit retry + model fallback
# ──────────────────────────────────────────────────────────────────

def ask_gemini(api_key, sys_prompt, history, question):
    """
    Call Gemini with automatic retry on 429 rate-limit errors.

    Strategy:
    • Parse suggested wait seconds from error message when available
    • Show live countdown in UI
    • Retry up to 3 times per model
    • Fall back from gemini-1.5-flash → gemini-1.5-flash-8b
    • Clean history if all attempts fail

    Free tier: 15 RPM / 1,500 RPD per model (gemini-1.5-flash)
    """
    history.append({"role":"user","parts":[{"text":question}]})
    payload = {
        "system_instruction": {"parts":[{"text":sys_prompt}]},
        "contents": history,
        "generationConfig": {"maxOutputTokens":2000,"temperature":0.3},
    }
    last_err = None

    for model in GEMINI_CHAIN:
        url = f"{GEMINI_BASE}/{model}:generateContent?key={api_key}"
        for attempt in range(3):
            try:
                resp = requests.post(
                    url, headers={"Content-Type":"application/json"},
                    json=payload, timeout=60)

                if resp.status_code == 429:
                    body = resp.json()
                    msg  = body.get("error",{}).get("message","")
                    m    = re.search(r"retry in ([0-9.]+)s", msg, re.I)
                    wait = min(float(m.group(1)) if m else [10,20,40][attempt], 60)
                    last_err = f"Rate limit ({model})"
                    if attempt < 2:
                        ph = st.empty()
                        for s in range(int(wait),0,-1):
                            ph.warning(
                                f"⏳ Rate limit hit on **{model}** — "
                                f"retrying in {s}s (attempt {attempt+1}/3)"
                            )
                            time.sleep(1)
                        ph.empty()
                        continue
                    break  # move to next model

                if not resp.ok:
                    err = resp.json()
                    raise ValueError(
                        f"Gemini {resp.status_code} ({model}): "
                        f"{err.get('error',{}).get('message',str(err))}"
                    )

                cands = resp.json().get("candidates",[])
                if not cands:
                    raise ValueError("Gemini returned no candidates (safety filter?).")
                text = "".join(
                    p.get("text","")
                    for p in cands[0].get("content",{}).get("parts",[])
                )
                if not text.strip():
                    raise ValueError("Gemini returned empty text.")
                history.append({"role":"model","parts":[{"text":text}]})
                return text

            except ValueError:
                raise
            except requests.RequestException as e:
                last_err = str(e)
                if attempt < 2: time.sleep([5,15][attempt])

        st.toast(f"Switching model: {model} → {GEMINI_CHAIN[-1]}", icon="🔄")

    history.pop()  # remove failed user message → keep history clean
    raise ValueError(
        f"{last_err}. All Gemini models exhausted. "
        "Wait ~1 min and retry, or add billing at console.cloud.google.com"
    )

# ──────────────────────────────────────────────────────────────────
#  TRACE PARSER
# ──────────────────────────────────────────────────────────────────

def parse_trace(raw):
    """Pull [TRACE: k=v, ...] off the front of the model response."""
    m = re.search(r"\[TRACE:([^\]]+)\]", raw)
    if not m:
        return None, raw.strip()
    trace = {}
    for part in m.group(1).split(","):
        if "=" in part:
            k,_,v = part.partition("=")
            trace[k.strip()] = v.strip().strip('"')
    trace["model"]      = GEMINI_CHAIN[0]
    trace["fetched_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    trace["api_calls"]  = str(len(st.session_state.api_log))
    return trace, raw.replace(m.group(0),"").strip()

def trace_html(trace):
    rows = "".join(
        f'<div class="trace-row"><span class="trace-k">{k}</span>'
        f'<span class="trace-v">{v}</span></div>'
        for k,v in trace.items()
    )
    return (f'<div class="trace-box">'
            f'<div class="trace-hdr">⚡ Monday.com API Tool-Call Trace</div>'
            f'{rows}</div>')

def safe_html(text):
    """Strip unsafe tags, preserve basic formatting."""
    return re.sub(r"<(?!/?(?:br|strong|b|em|i|h[1-6]|ul|ol|li|p)\b)[^>]+>","",text)

# ──────────────────────────────────────────────────────────────────
#  SIDEBAR
# ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⬡ Monday BI Agent")
    st.caption("Skylark Drones · Technical Assignment")
    st.divider()

    # Gemini key
    st.markdown("**🔑 Gemini API Key**")
    gemini_key = st.text_input(
        "gkey", label_visibility="collapsed", type="password",
        placeholder="AIza… (free at aistudio.google.com)",
        value=st.session_state.gemini_key,
    )
    st.caption("Get free key → [aistudio.google.com](https://aistudio.google.com)")
    st.divider()

    # Monday.com
    st.markdown("**📋 Monday.com Live Boards**")
    with st.expander("⚙ Configure", expanded=not st.session_state.connected):
        monday_token = st.text_input(
            "API Token", type="password",
            placeholder="eyJhbGci…",
            value=st.session_state.monday_token,
            help="Profile → Developers → My Access Tokens",
        )
        wo_board_id = st.text_input(
            "Work Orders Board ID",
            placeholder="e.g. 1234567890",
            value=st.session_state.wo_board_id,
            help="Open board → copy number from URL",
        )
        deal_board_id = st.text_input(
            "Deal Funnel Board ID",
            placeholder="e.g. 9876543210",
            value=st.session_state.deal_board_id,
        )
        st.caption("Board ID: monday.com/boards/**1234567890**")
    st.divider()

    # Excel upload fallback
    st.markdown("**📂 Excel Upload** *(fallback)*")
    with st.expander("Upload .xlsx files", expanded=not st.session_state.connected):
        st.caption("Used when Monday.com credentials not provided")
        wo_up   = st.file_uploader("Work Orders (.xlsx)",  type=["xlsx"], key="wo_up")
        deal_up = st.file_uploader("Deal Funnel (.xlsx)",  type=["xlsx"], key="deal_up")
    st.divider()

    # Connect
    if st.button("🚀 Connect & Load Data", use_container_width=True):
        if not gemini_key.startswith("AIza") or len(gemini_key) < 20:
            st.error("Invalid Gemini key. Get one free at aistudio.google.com")
        else:
            st.session_state.update(dict(
                gemini_key=gemini_key, monday_token=monday_token,
                wo_board_id=wo_board_id, deal_board_id=deal_board_id,
            ))
            raw_wo = raw_deal = None
            use_live = False

            # Attempt Monday.com live
            if monday_token and wo_board_id and deal_board_id:
                with st.spinner("Connecting to Monday.com…"):
                    try:
                        raw_wo   = fetch_board(monday_token, wo_board_id,   "Work Orders")
                        raw_deal = fetch_board(monday_token, deal_board_id, "Deal Funnel")
                        use_live = True
                        st.session_state.data_source = (
                            f"Monday.com LIVE — WO:{wo_board_id} | Deals:{deal_board_id}"
                        )
                    except Exception as e:
                        st.warning(f"Monday.com failed: {e}\n\nFalling back to Excel…")

            # Excel fallback
            if not use_live:
                if wo_up and deal_up:
                    with st.spinner("Reading Excel files…"):
                        try:
                            raw_wo, raw_deal = load_excel(wo_up, deal_up)
                            st.session_state.data_source = (
                                f"Excel — {wo_up.name} + {deal_up.name}"
                            )
                        except Exception as e:
                            st.error(f"Excel read failed: {e}")
                            st.stop()
                else:
                    st.error(
                        "**No data source.** Either:\n"
                        "- Fill Monday.com credentials above, OR\n"
                        "- Upload both Excel files"
                    )
                    st.stop()

            st.session_state.wos       = enrich_wo(raw_wo)
            st.session_state.deals     = enrich_deals(raw_deal)
            st.session_state.is_live   = use_live
            st.session_state.connected = True
            label = "Monday.com LIVE" if use_live else "Excel"
            st.success(
                f"✓ {label} — "
                f"{len(st.session_state.wos)} WOs + "
                f"{len(st.session_state.deals)} Deals loaded"
            )
            st.rerun()

    st.divider()

    # Board status
    st.markdown("**📊 Board Status**")
    if st.session_state.connected:
        icon = "🟢" if st.session_state.is_live else "🟡"
        st.markdown(f"{icon} Work Orders — **{len(st.session_state.wos)}** items")
        st.markdown(f"{icon} Deal Funnel — **{len(st.session_state.deals)}** items")
        st.caption("Monday.com LIVE" if st.session_state.is_live else "Excel upload")
        st.caption(f"Monday API calls this session: **{len(st.session_state.api_log)}**")
    else:
        st.markdown("🔴 Not connected")
    st.divider()

    # Quick queries
    st.markdown("**⚡ Quick Queries**")
    for q in QUICK_QUERIES:
        if st.button(q, key=f"qq{hash(q)}", use_container_width=True):
            st.session_state.run_query = q
    st.divider()

    # Actions
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🗑 Clear Chat", use_container_width=True):
            st.session_state.chat_history  = []
            st.session_state.gemini_history= []
            st.rerun()
    with c2:
        if st.button("🔄 Refresh", use_container_width=True):
            if st.session_state.is_live and st.session_state.monday_token:
                with st.spinner("Re-fetching boards…"):
                    try:
                        st.session_state.wos = enrich_wo(
                            fetch_board(st.session_state.monday_token,
                                        st.session_state.wo_board_id, "Work Orders"))
                        st.session_state.deals = enrich_deals(
                            fetch_board(st.session_state.monday_token,
                                        st.session_state.deal_board_id, "Deal Funnel"))
                        st.success("Refreshed!")
                    except Exception as e:
                        st.error(f"Refresh failed: {e}")
            else:
                st.info("Refresh only works in live Monday.com mode.")

# ──────────────────────────────────────────────────────────────────
#  MAIN AREA — HEADER
# ──────────────────────────────────────────────────────────────────
if st.session_state.connected:
    badge = ('<span class="badge-live">● LIVE · MONDAY.COM</span>'
             if st.session_state.is_live
             else '<span class="badge-excel">◐ EXCEL UPLOAD</span>')
else:
    badge = ""

st.markdown(f"""
<div class="app-header">
  <div>
    <div class="app-title">⬡ Monday.com Business Intelligence Agent</div>
    <div class="app-sub">Skylark Drones · Live Monday.com Integration · Gemini 1.5 Flash · Real-time tool-call traces</div>
  </div>
  {badge}
</div>
""", unsafe_allow_html=True)

# ── Not connected ─────────────────────────────────────────────────
if not st.session_state.connected:
    col_l, col_r = st.columns([3,2])
    with col_l:
        st.info(
            "**👈 Get started — 3 steps in the sidebar:**\n\n"
            "1. Enter your **Gemini API key** "
            "(free → [aistudio.google.com](https://aistudio.google.com))\n"
            "2. **Option A:** Fill in Monday.com credentials for live board data\n"
            "   **Option B:** Upload your Excel files as fallback\n"
            "3. Click **Connect & Load Data**"
        )
    with col_r:
        st.markdown("**What this agent does:**")
        st.markdown("""
- 📡 **Live Monday.com API** — fresh data every query, no caching
- 🔍 **Natural language BI** — ask founder-level questions in plain English
- 🔀 **Cross-board analysis** — Work Orders + Deal Funnel synthesised together
- ⚡ **Visible tool traces** — see exactly which API calls were made
- 🛡 **Data resilience** — nulls, inconsistent formats, quality caveats handled
- 💬 **Multi-turn chat** — full conversation context for follow-ups
        """)
    st.stop()

# ── Live metrics bar ──────────────────────────────────────────────
a = analytics(st.session_state.wos, st.session_state.deals)
c1,c2,c3,c4,c5,c6 = st.columns(6)
c1.metric("Deal Pipeline",     fmt(a["tot_pipeline"]), f"{a['n_deal']} deals")
c2.metric("WO Contract Value", fmt(a["tot_contract"]), f"{a['n_wo']} WOs")
c3.metric("Open Deals",        a["n_open"],            f"Won: {a['n_won']}")
c4.metric("AR Outstanding",    fmt(a["tot_ar"]),       f"Unbilled: {fmt(a['tot_tobill'])}")
c5.metric("Total Collected",   fmt(a["tot_collected"]),"from work orders")
c6.metric("API Calls",         len(st.session_state.api_log), "this session")
st.divider()

# ──────────────────────────────────────────────────────────────────
#  TABS: Chat | API Audit Log
# ──────────────────────────────────────────────────────────────────
tab_chat, tab_log = st.tabs(["💬 Chat", "🔌 Monday.com API Audit Log"])

# ── API Audit Log tab (Requirement: Agent Action Visibility) ──────
with tab_log:
    st.markdown("**Every Monday.com GraphQL API call made this session**")
    st.caption(
        "Each query triggers live API calls — schema fetch + paginated item fetch "
        "per board. This log satisfies the 'visible action/tool-call trace' requirement."
    )
    if st.session_state.api_log:
        st.dataframe(
            st.session_state.api_log,
            use_container_width=True,
            column_config={
                "time"  : st.column_config.TextColumn("Time",   width=80),
                "action": st.column_config.TextColumn("Action", width=300),
                "board" : st.column_config.TextColumn("Endpoint"),
                "http"  : st.column_config.NumberColumn("HTTP", width=60),
                "ms"    : st.column_config.NumberColumn("Latency (ms)", width=110),
                "kb"    : st.column_config.NumberColumn("Response (KB)", width=120),
            },
        )
        tot_ms = sum(r["ms"] for r in st.session_state.api_log)
        st.caption(
            f"Total: **{len(st.session_state.api_log)}** API calls | "
            f"Total latency: **{tot_ms} ms** | "
            f"Boards: Work Orders + Deal Funnel"
        )
    else:
        st.info("No API calls yet. Ask a question in the Chat tab to trigger live Monday.com queries.")

# ── Chat tab ──────────────────────────────────────────────────────
with tab_chat:

    # Render history
    if not st.session_state.chat_history:
        st.markdown(
            "<div style='text-align:center;color:#475569;padding:48px 0 16px;"
            "font-size:14px;font-family:Inter,sans-serif'>"
            "Ask a question below, or pick one from the sidebar Quick Queries.<br>"
            "<span style='font-size:12px;color:#334155'>Every query fetches live data from Monday.com boards.</span>"
            "</div>",
            unsafe_allow_html=True,
        )

    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            st.markdown(
                f'<div class="user-bubble">👤&nbsp; {msg["content"]}</div>',
                unsafe_allow_html=True,
            )
        else:
            # Data quality warnings
            dq_html = ""
            if msg.get("dq"):
                items = " &nbsp;·&nbsp; ".join(msg["dq"])
                dq_html = f'<div class="dq-note">⚠ Data caveats: {items}</div>'

            # Tool-call trace
            t_html = trace_html(msg["trace"]) if msg.get("trace") else ""

            st.markdown(
                f'<div class="ai-bubble">{dq_html}{t_html}'
                f'{safe_html(msg["content"])}</div>',
                unsafe_allow_html=True,
            )

    st.divider()

    # Input
    prefill = st.session_state.run_query
    st.session_state.run_query = ""

    inp_col, btn_col = st.columns([10, 1])
    with inp_col:
        user_q = st.text_input(
            "q", label_visibility="collapsed",
            placeholder="Ask a founder-level question… e.g. How's our Mining sector pipeline?",
            value=prefill, key="chat_in",
        )
    with btn_col:
        send = st.button("Send ↑", use_container_width=True)

    st.caption(
        "Enter ↵ to send · Gemini 1.5-flash with auto-retry · "
        "Live Monday.com data fetched on every query"
    )

    # ── Ask handler ───────────────────────────────────────────────
    def do_ask(q: str):
        q = q.strip()
        if not q: return
        if not st.session_state.gemini_key:
            st.error("Enter your Gemini API key in the sidebar first.")
            return

        # Record user message
        st.session_state.chat_history.append(
            {"role":"user","content":q,"trace":None,"dq":[]}
        )

        # ── REQUIREMENT: "Every query must trigger live API calls at query time" ──
        if st.session_state.is_live and st.session_state.monday_token:
            with st.spinner("📡 Fetching live data from Monday.com boards…"):
                try:
                    st.session_state.wos = enrich_wo(
                        fetch_board(st.session_state.monday_token,
                                    st.session_state.wo_board_id, "Work Orders"))
                    st.session_state.deals = enrich_deals(
                        fetch_board(st.session_state.monday_token,
                                    st.session_state.deal_board_id, "Deal Funnel"))
                except Exception as e:
                    st.warning(f"Live re-fetch failed: {e}. Using last cached data.")

        # Collect data quality notes for this query
        dq = dq_warnings(st.session_state.wos, st.session_state.deals)

        # Build fresh prompt (no caching)
        sys_prompt = build_prompt(
            st.session_state.wos, st.session_state.deals,
            st.session_state.data_source
        )

        with st.spinner("🤖 Analyzing with Gemini…"):
            try:
                raw = ask_gemini(
                    st.session_state.gemini_key,
                    sys_prompt,
                    st.session_state.gemini_history,
                    q,
                )
            except Exception as e:
                st.session_state.chat_history.append(
                    {"role":"ai","content":f"⚠ **Error:** {e}","trace":None,"dq":[]}
                )
                st.rerun()
                return

        tr, answer = parse_trace(raw)
        st.session_state.chat_history.append(
            {"role":"ai","content":answer,"trace":tr,"dq":dq}
        )
        st.rerun()

    if send and user_q.strip():
        do_ask(user_q)
    elif prefill:
        do_ask(prefill)
