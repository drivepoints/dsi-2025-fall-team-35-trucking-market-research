import os, re, csv, time, random, asyncio, sqlite3
from contextlib import closing
from pathlib import Path

import aiohttp
import pandas as pd
from bs4 import BeautifulSoup

# --------------- CONFIG ---------------
INPUT_CSV   = "../data/sample-for-annotation-400.csv"
OUTPUT_CSV  = "../data/enriched_400_safer_snapshot.csv"

CONCURRENCY     = 5       # be polite to FMCSA
RATE_PER_SEC    = 2        # 2 POSTs/sec total
CONNECT_TIMEOUT = 20
READ_TIMEOUT    = 20
RETRIES         = 2
BATCH_SIZE      = 25 # save every 25

POST_URL = "https://safer.fmcsa.dot.gov/query.asp"
OUT_FIELDS = ["dot_number", "usdot_status", "cargo_types"]
# OUT_FIELDS = [
#     "dot_number",
#     "usdot_status",
#     "cargo_types",
    # "out_of_service_date",
    # "operating_authority_status",
    # "inspections_24mo_vehicle",
    # "inspections_24mo_driver",
    # "inspections_24mo_hazmat",
    # "oos_pct_vehicle",
    # "oos_pct_driver",
    # "oos_pct_hazmat",
    # "crashes_24mo_fatal",
    # "crashes_24mo_injury",
    # "crashes_24mo_tow",
    # "crashes_24mo_total",
# ]

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]

# ---------------- RATE LIMITER ----------------
class RateLimiter:
    def __init__(self, rate): self.gap, self.last = 1 / rate, 0
    async def __aenter__(self):
        await asyncio.sleep(max(0, self.gap - (time.time() - self.last)))
        self.last = time.time()
    async def __aexit__(self, *args): pass

# ---------------- PARSING ----------------
def parse_usdot_status(soup):
    tag = soup.find("th", string=lambda s: s and "USDOT Status" in s)
    return tag.find_next("td").get_text(strip=True) if tag else ""

def parse_cargo_types(soup):
    cargo_header = soup.find("a", href=lambda x: x and "Cargo" in x) \
        or soup.find("th", string=lambda s: s and "Cargo Carried" in s)
    table = cargo_header.find_next("table") if cargo_header else None
    if not table: return ""
    cargos = [tds[1].get_text(strip=True)
              for tr in table.find_all("tr")
              if (tds := tr.find_all("td")) and len(tds) >= 2
              and tds[0].get_text(strip=True).strip().upper() == "X"]
    return "; ".join(sorted(set(cargos)))

def parse_snapshot_html(html):
    if not html: return {"usdot_status": "", "cargo_types": ""}
    soup = BeautifulSoup(html, "html.parser")
    return {
        "usdot_status": parse_usdot_status(soup),
        "cargo_types": parse_cargo_types(soup),
    }

# ---------------- FETCH ----------------
async def fetch_snapshot_html(session, limiter, dot, logger=print):
    payload = {
        "searchtype": "ANY",
        "query_type": "queryCarrierSnapshot",
        "query_param": "USDOT",
        "query_string": str(dot),
    }
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Origin": "https://safer.fmcsa.dot.gov",
        "Referer": "https://safer.fmcsa.dot.gov/",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    backoff = 0.5
    for attempt in range(RETRIES):
        try:
            async with limiter:
                async with session.post(POST_URL, data=payload, headers=headers) as resp:
                    html = await resp.text(errors="ignore")
                    if resp.status == 200 and len(html) > 10000:
                        logger(f"[ok] DOT {dot} len={len(html)}")
                        return html
                    logger(f"[warn] DOT {dot} status={resp.status} len={len(html)}")
        except Exception as e:
            logger(f"[err] DOT {dot}: {e}")
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, 30)
    return ""

# ---------------- CSV ----------------
def flush_rows(path, rows):
    if not rows: return
    write_header = not Path(path).exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=OUT_FIELDS)
        if write_header: w.writeheader()
        w.writerows(rows)

# ---------------- WORKER ----------------
async def worker(name, q, limiter, session, results_lock):
    buffer = []
    while True:
        dot = await q.get()
        if dot is None:
            q.task_done()
            break
        html = await fetch_snapshot_html(session, limiter, dot)
        parsed = parse_snapshot_html(html)
        buffer.append({"dot_number": dot, **parsed})

        # ✅ batch save every BATCH_SIZE
        if len(buffer) >= BATCH_SIZE:
            async with results_lock:
                flush_rows(OUTPUT_CSV, buffer)
            buffer.clear()

        q.task_done()

    # save leftovers
    if buffer:
        async with results_lock:
            flush_rows(OUTPUT_CSV, buffer)
    print(f"[worker-{name}] done")

# ---------------- MAIN ----------------
async def main():
    df = pd.read_csv(INPUT_CSV, dtype=str)
    df.columns = df.columns.str.lower()
    dots = df["dot_number"].dropna().astype(str).tolist()

    limiter = RateLimiter(RATE_PER_SEC)
    timeout = aiohttp.ClientTimeout(total=CONNECT_TIMEOUT + READ_TIMEOUT)
    connector = aiohttp.TCPConnector(limit=CONCURRENCY)
    q = asyncio.Queue()
    results_lock = asyncio.Lock()

    [q.put_nowait(d) for d in dots]
    [q.put_nowait(None) for _ in range(CONCURRENCY)]

    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        tasks = [asyncio.create_task(worker(i, q, limiter, session, results_lock))
                 for i in range(CONCURRENCY)]
        await q.join()
        await asyncio.gather(*tasks, return_exceptions=True)

    print(f"✅ Finished {len(dots)} DOT numbers and saved output to {OUTPUT_CSV}")

if __name__ == "__main__":
    asyncio.run(main())