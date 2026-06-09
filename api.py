"""
FastAPI Server for Seymour Duncan Stripe Auth Checker
Run with: uvicorn api:app --host 0.0.0.0 --port 8000 --reload
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import uvicorn
import psycopg2
import psycopg2.extras
from datetime import datetime
import os
import sys
from contextlib import asynccontextmanager

from seymour_duncan import SeymourDuncanGateway

# ─────────────────────────────────────────────────────────
# Database
# ─────────────────────────────────────────────────────────
DB_URL = os.getenv(
    "DB_URL",
    "postgresql://neondb_owner:npg_SmFU7X5PYHiK@ep-purple-grass-apin5qq8.c-7.us-east-1.aws.neon.tech/neondb?sslmode=require"
)

def get_db():
    return psycopg2.connect(DB_URL)

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS card_checks (
            id          SERIAL PRIMARY KEY,
            card        VARCHAR(50),
            status      VARCHAR(50),
            message     TEXT,
            response    TEXT,
            time_taken  FLOAT,
            gateway     VARCHAR(100),
            checked_at  TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

def save_card_result(card: str, status: str, message: str, response: str, time_taken: float, gateway: str):
    """Save result to DB — skipped if status is Declined."""
    if status == "Declined":
        return
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO card_checks (card, status, message, response, time_taken, gateway)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (card, status, message, str(response)[:500], time_taken, gateway)
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[DB ERROR] {e}")


# ─────────────────────────────────────────────────────────
# /page  — beautiful branded docs
# ─────────────────────────────────────────────────────────
PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LEVIATHAN API</title>
<link href="https://fonts.googleapis.com/css2?family=Cinzel+Decorative:wght@900&family=Cinzel:wght@400;700&family=Share+Tech+Mono&display=swap" rel="stylesheet">
<script src="https://unpkg.com/lucide@latest/dist/umd/lucide.js"></script>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: #060612;
    color: #c9d1e0;
    font-family: 'Share Tech Mono', monospace;
    min-height: 100vh;
  }

  /* ── hero ── */
  .hero {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 70px 20px 50px;
    text-align: center;
    position: relative;
    overflow: hidden;
  }
  .hero::before {
    content: '';
    position: absolute;
    inset: 0;
    background: radial-gradient(ellipse 80% 60% at 50% 0%, rgba(94,0,255,.28) 0%, transparent 70%);
    pointer-events: none;
  }

  .brand {
    font-family: 'Cinzel Decorative', serif;
    font-size: clamp(2.8rem, 9vw, 7rem);
    font-weight: 900;
    letter-spacing: .08em;
    background: linear-gradient(135deg, #a855f7 0%, #6366f1 40%, #06b6d4 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    text-shadow: none;
    filter: drop-shadow(0 0 32px rgba(168,85,247,.55));
    line-height: 1.1;
    user-select: none;
  }

  .tagline {
    font-family: 'Cinzel', serif;
    font-size: clamp(.85rem, 2.2vw, 1.1rem);
    letter-spacing: .35em;
    color: #7c83a0;
    margin-top: 14px;
    text-transform: uppercase;
  }

  .coder {
    margin-top: 22px;
    display: inline-block;
    font-family: 'Share Tech Mono', monospace;
    font-size: .95rem;
    color: #a855f7;
    border: 1px solid rgba(168,85,247,.35);
    border-radius: 999px;
    padding: 5px 22px;
    letter-spacing: .12em;
    background: rgba(168,85,247,.07);
  }

  /* ── divider ── */
  .divider {
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(99,102,241,.5), transparent);
    margin: 0 auto;
    max-width: 860px;
  }

  /* ── content ── */
  .content {
    max-width: 860px;
    margin: 0 auto;
    padding: 48px 24px 80px;
  }

  h2 {
    font-family: 'Cinzel', serif;
    font-size: 1.15rem;
    color: #818cf8;
    letter-spacing: .15em;
    text-transform: uppercase;
    margin: 44px 0 18px;
    border-left: 3px solid #6366f1;
    padding-left: 14px;
    display: flex;
    align-items: center;
    gap: 10px;
  }
  h2 svg { width: 17px; height: 17px; stroke: #6366f1; flex-shrink: 0; }

  p { line-height: 1.75; color: #9ca3af; margin-bottom: 12px; }

  /* ── endpoint cards ── */
  .ep {
    background: rgba(255,255,255,.03);
    border: 1px solid rgba(99,102,241,.18);
    border-radius: 10px;
    padding: 18px 22px;
    margin-bottom: 14px;
    transition: border-color .2s;
  }
  .ep:hover { border-color: rgba(168,85,247,.45); }

  .ep-header { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; flex-wrap: wrap; }

  .badge {
    font-size: .72rem;
    font-weight: 700;
    padding: 3px 10px;
    border-radius: 5px;
    letter-spacing: .06em;
  }
  .get  { background: #064e3b; color: #34d399; }
  .post { background: #1e1b4b; color: #a5b4fc; }

  .ep-path {
    font-family: 'Share Tech Mono', monospace;
    font-size: 1rem;
    color: #e2e8f0;
  }

  .ep-desc { color: #6b7280; font-size: .88rem; margin-bottom: 10px; }

  .params { margin-top: 8px; }
  .param-row {
    display: grid;
    grid-template-columns: 160px 1fr;
    gap: 6px 14px;
    font-size: .83rem;
    padding: 5px 0;
    border-bottom: 1px solid rgba(255,255,255,.04);
  }
  .param-row:last-child { border-bottom: none; }
  .param-name { color: #c084fc; }
  .param-desc { color: #6b7280; }

  /* ── code block ── */
  .code-block {
    background: #0d0d1a;
    border: 1px solid rgba(99,102,241,.2);
    border-radius: 8px;
    padding: 16px 20px;
    font-size: .83rem;
    overflow-x: auto;
    white-space: pre;
    color: #a5b4fc;
    margin: 10px 0 18px;
    line-height: 1.6;
  }

  .highlight { color: #34d399; }
  .hl-key   { color: #f472b6; }
  .hl-str   { color: #fbbf24; }

  /* ── status table ── */
  .status-table { width: 100%; border-collapse: collapse; font-size: .88rem; margin-top: 8px; }
  .status-table th {
    text-align: left; padding: 8px 14px;
    background: rgba(99,102,241,.12);
    color: #818cf8;
    font-family: 'Cinzel', serif;
    letter-spacing: .08em;
    font-size: .78rem;
  }
  .status-table td { padding: 9px 14px; border-bottom: 1px solid rgba(255,255,255,.04); color: #9ca3af; }
  .s-approved { color: #34d399; font-weight: 700; }
  .s-live     { color: #fbbf24; font-weight: 700; }
  .s-declined { color: #f87171; font-weight: 700; }
  .s-error    { color: #fb923c; font-weight: 700; }

  /* ── footer ── */
  footer {
    text-align: center;
    padding: 30px 20px;
    font-size: .78rem;
    color: #374151;
    border-top: 1px solid rgba(255,255,255,.04);
    letter-spacing: .08em;
  }
</style>
</head>
<body>

<!-- HERO -->
<div class="hero">
  <div class="brand">LEVIATHAN</div>
  <div class="tagline">Stripe Auth Intelligence API</div>
  <div class="coder">CODER: @COMMANDO69</div>
</div>

<div class="divider"></div>

<div class="content">

  <h2><i data-lucide="info"></i> Overview</h2>
  <p>LEVIATHAN is a high-performance card-auth checking API powered by the Seymour Duncan gateway. Submit card details via GET or POST — live and approved results are persisted to the database; declined cards are not stored.</p>

  <!-- ────────── ENDPOINTS ────────── -->
  <h2><i data-lucide="terminal"></i> Endpoints</h2>

  <!-- health -->
  <div class="ep">
    <div class="ep-header">
      <span class="badge get">GET</span>
      <span class="ep-path">/health</span>
    </div>
    <div class="ep-desc">Returns server and gateway status.</div>
    <div class="code-block"><span class="highlight">GET</span> /health

<span class="hl-key">Response:</span>
<span class="hl-str">{ "status": "ok", "gateway": "Seymour Duncan" }</span></div>
  </div>

  <!-- check_get -->
  <div class="ep">
    <div class="ep-header">
      <span class="badge get">GET</span>
      <span class="ep-path">/check_get</span>
    </div>
    <div class="ep-desc">Check a single card via URL query params — easy to use from the browser address bar.</div>
    <div class="params">
      <div class="param-row"><span class="param-name">number</span><span class="param-desc">Card number (13-19 digits)</span></div>
      <div class="param-row"><span class="param-name">month</span><span class="param-desc">Expiry month (1-12)</span></div>
      <div class="param-row"><span class="param-name">year</span><span class="param-desc">Expiry year (2 or 4 digits)</span></div>
      <div class="param-row"><span class="param-name">cvv</span><span class="param-desc">Card CVV / CVC (3-4 digits)</span></div>
    </div>
    <div class="code-block"><span class="highlight">GET</span> /check_get?number=4111111111111111&month=12&year=28&cvv=123</div>
  </div>

  <!-- check POST -->
  <div class="ep">
    <div class="ep-header">
      <span class="badge post">POST</span>
      <span class="ep-path">/check</span>
    </div>
    <div class="ep-desc">Check a single card via JSON body. Supports both field-by-field and pipe-delimited raw format.</div>
    <div class="code-block"><span class="highlight">POST</span> /check
<span class="hl-key">Content-Type:</span> application/json

<span class="hl-key">Option A — fields:</span>
{
  <span class="hl-str">"number"</span>: <span class="hl-str">"4111111111111111"</span>,
  <span class="hl-str">"month"</span>:  <span class="hl-str">"12"</span>,
  <span class="hl-str">"year"</span>:   <span class="hl-str">"28"</span>,
  <span class="hl-str">"cvv"</span>:    <span class="hl-str">"123"</span>
}

<span class="hl-key">Option B — raw pipe format:</span>
{ <span class="hl-str">"raw"</span>: <span class="hl-str">"4111111111111111|12|28|123"</span> }</div>
  </div>

  <!-- check_bulk POST -->
  <div class="ep">
    <div class="ep-header">
      <span class="badge post">POST</span>
      <span class="ep-path">/check_bulk</span>
    </div>
    <div class="ep-desc">Check multiple cards in one request. Returns per-card results plus a summary.</div>
    <div class="code-block"><span class="highlight">POST</span> /check_bulk
<span class="hl-key">Content-Type:</span> application/json

{
  <span class="hl-str">"cards"</span>: [
    { <span class="hl-str">"number"</span>: <span class="hl-str">"4111111111111111"</span>, <span class="hl-str">"month"</span>: <span class="hl-str">"12"</span>, <span class="hl-str">"year"</span>: <span class="hl-str">"28"</span>, <span class="hl-str">"cvv"</span>: <span class="hl-str">"123"</span> },
    { <span class="hl-str">"raw"</span>: <span class="hl-str">"5500005555555559|06|27|321"</span> }
  ]
}</div>
  </div>

  

  <!-- ────────── EXAMPLE RESPONSE ────────── -->
  <h2><i data-lucide="code-2"></i> Example Response</h2>
  <div class="code-block">{
  <span class="hl-str">"card"</span>:    <span class="hl-str">"411111******1111"</span>,
  <span class="hl-str">"success"</span>: <span class="highlight">true</span>,
  <span class="hl-str">"status"</span>:  <span class="hl-str">"Approved"</span>,
  <span class="hl-str">"message"</span>: <span class="hl-str">"Payment method successfully added"</span>,
  <span class="hl-str">"response"</span>: <span class="hl-str">"Payment method successfully added"</span>,
  <span class="hl-str">"time"</span>:    <span class="highlight">4.21</span>,
  <span class="hl-str">"gateway"</span>: <span class="hl-str">"Seymour Duncan"</span>
}</div>

</div><!-- /content -->

<footer>LEVIATHAN &nbsp;|&nbsp; CODER: @COMMANDO69 &nbsp;|&nbsp; ALL RIGHTS RESERVED</footer>
<script>lucide.createIcons();</script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────
@asynccontextmanager
def lifespan(app: FastAPI):
    init_db()
    base_port = os.getenv("PORT", "8000")
    base_url = os.getenv("BASE_URL", f"http://localhost:{base_port}")
    print("=" * 50)
    print("  LEVIATHAN - Stripe Auth API  |  CODER: @COMMANDO69")
    print("=" * 50)
    print(f"  Docs:    {base_url}/page")
    print(f"  Swagger: {base_url}/docs")
    print(f"  Health:  {base_url}/health")
    print("=" * 50)
    yield

app = FastAPI(
    title="LEVIATHAN — Stripe Auth API",
    description="Card auth checking via Seymour Duncan gateway with PostgreSQL persistence.",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

gateway = SeymourDuncanGateway()


# ─────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────
class CardCheckRequest(BaseModel):
    number: str = ""
    month: str = ""
    year: str = ""
    cvv: str = ""
    raw: str | None = None


class BulkCardCheckRequest(BaseModel):
    cards: list[CardCheckRequest]


# ─────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────
def mask(number: str) -> str:
    n = number.replace(" ", "")
    return n[:6] + "******" + n[-4:] if len(n) >= 10 else n

def process_result(raw_str: str) -> dict:
    parts = raw_str.split("|")
    result = gateway.check_card(card_str=raw_str)
    masked = mask(parts[0])
    status  = result.get("status", "Unknown")
    message = result.get("message", "")
    resp    = result.get("response", "")
    elapsed = result.get("time", 0)
    gw      = result.get("gateway", gateway.name)
    save_card_result(masked, status, str(message), str(resp), elapsed, gw)
    return {
        "card":     masked,
        "success":  result.get("success", False),
        "status":   status,
        "message":  message,
        "response": resp,
        "time":     elapsed,
        "gateway":  gw,
    }


# ─────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────
@app.get("/", response_class=JSONResponse)
def root():
    return {"message": "LEVIATHAN API — visit /page for instructions, /docs for Swagger."}


@app.get("/page", response_class=HTMLResponse)
def page():
    return PAGE_HTML


@app.get("/health")
def health():
    return {"status": "ok", "gateway": gateway.name}


@app.get("/check_get")
def check_get(
    number: str = Query(..., description="Card number"),
    month:  str = Query(..., description="Expiry month"),
    year:   str = Query(..., description="Expiry year"),
    cvv:    str = Query(..., description="CVV"),
):
    raw_str = f"{number}|{month}|{year}|{cvv}"
    return process_result(raw_str)


@app.post("/check")
def check_card(card: CardCheckRequest):
    if card.raw:
        raw_str = card.raw.strip()
    else:
        if not all([card.number, card.month, card.year, card.cvv]):
            raise HTTPException(400, "Provide number+month+year+cvv or raw (pipe-delimited)")
        raw_str = f"{card.number}|{card.month}|{card.year}|{card.cvv}"
    if len(raw_str.split("|")) < 4:
        raise HTTPException(400, "Invalid format. Use: number|month|year|cvv")
    return process_result(raw_str)


@app.post("/check_bulk")
def check_bulk(req: BulkCardCheckRequest):
    results = []
    successes = failures = 0
    for card in req.cards:
        if card.raw:
            raw_str = card.raw.strip()
        else:
            raw_str = f"{card.number}|{card.month}|{card.year}|{card.cvv}"
        entry = process_result(raw_str)
        results.append(entry)
        if entry["success"]:
            successes += 1
        else:
            failures += 1
    return {"total": len(results), "successes": successes, "failures": failures, "results": results}


@app.get("/results")
def get_results(limit: int = 50, offset: int = 0):
    limit = min(limit, 200)
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT * FROM card_checks ORDER BY checked_at DESC LIMIT %s OFFSET %s",
            (limit, offset)
        )
        rows = cur.fetchall()
        cur.execute("SELECT COUNT(*) FROM card_checks")
        total = cur.fetchone()["count"]
        cur.close()
        conn.close()
        return {"total": total, "limit": limit, "offset": offset, "results": [dict(r) for r in rows]}
    except Exception as e:
        raise HTTPException(500, f"Database error: {e}")


# ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    port_arg = None
    if len(sys.argv) > 1:
        try:
            port_arg = int(sys.argv[1])
        except ValueError:
            port_arg = None

    port = port_arg or int(os.getenv("PORT", 8000))
    print(f"Starting on http://0.0.0.0:{port} (PORT env={os.getenv('PORT')}, arg={sys.argv[1] if len(sys.argv) > 1 else None})")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
    )
