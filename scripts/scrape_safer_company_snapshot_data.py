import os, re, csv, time, random, asyncio, sqlite3
from contextlib import closing
from pathlib import Path

import aiohttp
import pandas as pd
from bs4 import BeautifulSoup

# --------------- CONFIG ---------------
INPUT_CSV   = "../data/100-sample-dots.csv"
OUTPUT_CSV  = "../data/enriched_100_safer_snapshot.csv"
CACHE_DB    = "../data/safer_snapshot_cache.sqlite"

CONCURRENCY     = 16       # be polite to FMCSA
RATE_PER_SEC    = 2        # 2 POSTs/sec total
CONNECT_TIMEOUT = 20
READ_TIMEOUT    = 30
RETRIES         = 5

POST_URL = "https://safer.fmcsa.dot.gov/query.asp"

# --------------- OUTPUT FIELDS ---------------
OUT_FIELDS = [
    "dot_number",
    "usdot_status",
    "out_of_service_date",
    "operating_authority_status",
    "cargo_types",
    "inspections_24mo_vehicle",
    "inspections_24mo_driver",
    "inspections_24mo_hazmat",
    "oos_pct_vehicle",
    "oos_pct_driver",
    "oos_pct_hazmat",
    "crashes_24mo_fatal",
    "crashes_24mo_injury",
    "crashes_24mo_tow",
    "crashes_24mo_total",
]

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]

# --------------- CACHE ---------------
def init_cache():
    with closing(sqlite3.connect(CACHE_DB)) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS html_cache (
            dot_number TEXT PRIMARY KEY,
            html TEXT NOT NULL)""")
        conn.commit()

def cache_get(dot):
    with closing(sqlite3.connect(CACHE_DB)) as conn:
        cur = conn.execute("SELECT html FROM html_cache WHERE dot_number = ?", (str(dot),))
        row = cur.fetchone()
        return row[0] if row else None

def cache_put(dot, html):
    with closing(sqlite3.connect(CACHE_DB)) as conn:
        conn.execute("INSERT OR REPLACE INTO html_cache(dot_number, html) VALUES (?, ?)", (str(dot), html))
        conn.commit()

# --------------- RATE LIMITER ---------------
class RateLimiter:
    def __init__(self, rate): self.rate, self._last = rate, 0
    async def wait(self):
        now, gap = time.time(), 1.0 / self.rate
        delta = now - self._last
        if delta < gap:
            await asyncio.sleep(gap - delta)
        self._last = time.time()

# --------------- FETCH HTML ---------------
async def fetch_snapshot_html_v2(session, limiter, dot_number, logger=print):
    cached = cache_get(dot_number)
    if cached:
        return cached

    await limiter.wait()
    payload = {
        "searchtype": "ANY",
        "query_type": "queryCarrierSnapshot",
        "query_param": "USDOT",
        "query_string": str(dot_number),
    }
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Origin": "https://safer.fmcsa.dot.gov",
        "Referer": "https://safer.fmcsa.dot.gov/",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    backoff = 0.5
    for attempt in range(1, RETRIES + 1):
        try:
            async with session.post(POST_URL, data=payload, headers=headers, allow_redirects=True) as resp:
                html = await resp.text(errors="ignore")
                if resp.status == 200 and len(html) > 10000:
                    logger(f"[ok] DOT {dot_number} len={len(html)}")
                    cache_put(dot_number, html)
                    return html
                logger(f"[warn] DOT {dot_number} status={resp.status} len={len(html)}")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)
        except Exception as e:
            logger(f"[err] DOT {dot_number} {e}")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)
    cache_put(dot_number, "")
    return ""

# --------------- PARSING ---------------
def _text(soup): return soup.get_text(" ", strip=True) if soup else ""

def parse_usdot_status(soup):
    tag = soup.find("th", string=lambda s: s and "USDOT Status" in s)
    if tag:
        td = tag.find_next("td")
        return td.get_text(strip=True) if td else ""
    return ""

def parse_out_of_service_date(soup):
    tag = soup.find("th", string=lambda s: s and "Out of Service Date" in s)
    if tag:
        td = tag.find_next("td")
        val = td.get_text(strip=True)
        return val if val and val.lower() != "none" else ""
    return ""

def parse_operating_authority_status(soup):
    tag = soup.find("th", string=lambda s: s and "Operating Authority Status" in s)
    if tag:
        td = tag.find_next("td")
        bold = td.find("b")
        if bold:
            return bold.get_text(strip=True)
        return td.get_text(" ", strip=True)
    return ""

def parse_cargo_types(soup):
    """Finds all cargo items marked with X in Cargo Carried section."""
    # find the header <th> with Cargo Carried
    cargo_header = soup.find("a", href=lambda x: x and "Cargo" in x)
    if not cargo_header:
        cargo_header = soup.find("th", string=lambda s: s and "Cargo Carried" in s)
    if not cargo_header:
        return ""
    table = cargo_header.find_next("table")
    cargos = []
    if table:
        for tr in table.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) >= 2:
                mark, label = tds[0].get_text(strip=True), tds[1].get_text(strip=True)
                if mark.upper() == "X" and label:
                    cargos.append(label)
    return "; ".join(sorted(set(cargos)))

def parse_snapshot_html(html: str):
    if not html:
        return {k: "" if "oos" not in k and "crashes" not in k else 0 for k in OUT_FIELDS[1:]}
    soup = BeautifulSoup(html, "html.parser")
    return {
        "usdot_status": parse_usdot_status(soup),
        "out_of_service_date": parse_out_of_service_date(soup),
        "operating_authority_status": parse_operating_authority_status(soup),
        "cargo_types": parse_cargo_types(soup)
    }

# --------------- WORKER ---------------
async def worker(dot_queue, results, limiter, session):
    while True:
        dot = await dot_queue.get()
        if dot is None:
            dot_queue.task_done()
            return
        try:
            html = await fetch_snapshot_html_v2(session, limiter, dot)
            parsed = parse_snapshot_html(html)
            results.append({"dot_number": dot, **parsed})
        except Exception as e:
            print(f"[err] DOT {dot}: {e}")
        finally:
            dot_queue.task_done()

def flush_rows(path, rows):
    write_header = not Path(path).exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=OUT_FIELDS)
        if write_header: w.writeheader()
        w.writerows(rows)

# --------------- MAIN ---------------
async def main():
    init_cache()
    df = pd.read_csv(INPUT_CSV, dtype=str)
    dots = df["dot_number"].dropna().astype(str).tolist()[:100]

    limiter = RateLimiter(RATE_PER_SEC)
    results = []
    timeout = aiohttp.ClientTimeout(total=CONNECT_TIMEOUT + READ_TIMEOUT)
    connector = aiohttp.TCPConnector(limit=CONCURRENCY)
    async with aiohttp.ClientSession(timeout=timeout, connector=connector,
                                     cookie_jar=aiohttp.CookieJar(unsafe=True)) as session:
        q = asyncio.Queue()
        for d in dots:
            await q.put(d)
        for _ in range(CONCURRENCY):
            await q.put(None)
        tasks = [asyncio.create_task(worker(q, results, limiter, session)) for _ in range(CONCURRENCY)]
        await q.join()
        for t in tasks:
            t.cancel()

    flush_rows(OUTPUT_CSV, results)
    print(f"Finished {len(results)} records → {OUTPUT_CSV}")

if __name__ == "__main__":
    asyncio.run(main())
