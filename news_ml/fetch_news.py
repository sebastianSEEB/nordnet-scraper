#!/usr/bin/env python3
"""
Henter børsmeldinger fra Oslo Børs Newsweb for aksjene i watchlisten
====================================================================
Inkrementelt: hver dag hentes bare én gang (siste dager hentes alltid på nytt,
i tilfelle meldinger kom inn sent). Meldingstekst hentes kun for meldinger
som modellen faktisk leser (kontrakter, innsidehandel, kvartalstall, oppkjøp).

Output:
    nordnet_data/news/messages_YYYY-MM.jsonl   én linje = én melding
    nordnet_data/news/state.json               hvilke dager som er hentet
    nordnet_data/news_ml/fetch_news_status.json  logg (lesbar fra GitHub)

Bruk:
    python news_ml/fetch_news.py                       # fra 2020-01-01 til i dag
    python news_ml/fetch_news.py --start 2024-01-01 --max-minutes 40
"""

import argparse
import glob
import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from news_ml.common import load_universe, NEWS_DIR, OUT_DIR, classify  # noqa: E402

LIST_URLS = [
    "https://api3.oslo.oslobors.no/v1/newsreader/list",
]
MSG_URLS = [
    "https://api3.oslo.oslobors.no/v1/newsreader/message",
]
HEADERS = {
    "User-Agent": "Mozilla/5.0 (research script; nordnet-scraper news_ml)",
    "Accept": "application/json",
    "Origin": "https://newsweb.oslobors.no",
    "Referer": "https://newsweb.oslobors.no/",
}
REFETCH_RECENT_DAYS = 3
BODY_KINDS = {"contract", "insider", "report", "mna", "guidance", "buyback"}


def get_json(session, urls, params, status, tries=3):
    last = None
    for url in urls:
        for attempt in range(tries):
            try:
                r = session.get(url, params=params, headers=HEADERS, timeout=30)
                last = f"{url} -> HTTP {r.status_code}"
                if r.status_code == 200:
                    return r.json()
                if r.status_code in (429, 500, 502, 503, 504):
                    time.sleep(2 + attempt * 3)
                    continue
                break
            except (requests.RequestException, ValueError) as e:
                last = f"{url} -> {type(e).__name__}: {e}"
                time.sleep(2 + attempt * 3)
    status["errors"].append(last)
    status["errors"] = status["errors"][-30:]
    return None


def extract_messages(js):
    """Newsweb har pakket svaret litt ulikt opp gjennom årene - vær tolerant."""
    if js is None:
        return None
    node = js
    for key in ("data", "messages"):
        if isinstance(node, dict) and key in node:
            node = node[key]
    if isinstance(node, dict):
        for v in node.values():
            if isinstance(v, list):
                return v
        return []
    return node if isinstance(node, list) else []


def norm_message(m):
    cats = m.get("category") or m.get("categories") or []
    if isinstance(cats, dict):
        cats = [cats]
    cat_txt = " | ".join(
        str(c.get("category_en") or c.get("category_no") or c.get("name") or c) if isinstance(c, dict) else str(c)
        for c in cats
    )
    return {
        "id": m.get("messageId") or m.get("id"),
        "news_id": m.get("newsId"),
        "published": m.get("publishedTime") or m.get("published") or m.get("publishedDate"),
        "issuer": (m.get("issuerSign") or m.get("issuer") or "").upper(),
        "issuer_name": m.get("issuerName") or "",
        "title": (m.get("title") or "").strip(),
        "category": cat_txt,
    }


def load_existing():
    rows = {}
    for path in sorted(glob.glob(os.path.join(NEWS_DIR, "messages_*.jsonl"))):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    r = json.loads(line)
                    rows[str(r["id"])] = r
    return rows


def save_all(rows):
    by_month = {}
    for r in rows.values():
        month = (r.get("published") or "0000-00")[:7]
        by_month.setdefault(month, []).append(r)
    for month, items in by_month.items():
        items.sort(key=lambda r: (r.get("published") or "", str(r["id"])))
        with open(os.path.join(NEWS_DIR, f"messages_{month}.jsonl"), "w", encoding="utf-8") as f:
            for r in items:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")


def html_to_text(s):
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s or "", flags=re.S | re.I)
    s = re.sub(r"<br\s*/?>|</p>|</div>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"&nbsp;", " ", s)
    s = re.sub(r"&amp;", "&", s)
    s = re.sub(r"[ \t]+", " ", s)
    return re.sub(r"\n\s*\n+", "\n", s).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2020-01-01")
    ap.add_argument("--end", default=date.today().isoformat())
    ap.add_argument("--max-minutes", type=float, default=45.0)
    ap.add_argument("--sleep", type=float, default=0.25)
    args = ap.parse_args()

    os.makedirs(NEWS_DIR, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)
    t0 = time.time()
    deadline = t0 + args.max_minutes * 60

    universe = load_universe()
    wanted = {u["issuer"] for u in universe}
    state_path = os.path.join(NEWS_DIR, "state.json")
    state = json.load(open(state_path)) if os.path.exists(state_path) else {"done_days": []}
    done = set(state.get("done_days", []))
    status = {"started": datetime.now(timezone.utc).isoformat(), "errors": [], "issuers_wanted": len(wanted)}

    rows = load_existing()
    session = requests.Session()

    # 1) Probe: virker API-et i det hele tatt? (skrives til status så feil synes på GitHub)
    probe_day = (date.today() - timedelta(days=1)).isoformat()
    probe = get_json(session, LIST_URLS, {"category": "", "issuer": "", "fromDate": probe_day,
                                          "toDate": probe_day, "market": "", "messageTitle": ""}, status)
    status["probe_ok"] = probe is not None
    status["probe_sample"] = str(probe)[:600] if probe is not None else None

    # 2) Dag for dag (API-et har tak per svar, én dag holder seg trygt under)
    d0, d1 = date.fromisoformat(args.start), date.fromisoformat(args.end)
    recent_cut = d1 - timedelta(days=REFETCH_RECENT_DAYS)
    days, d = [], d0
    while d <= d1:
        if d.weekday() < 5 or d >= recent_cut:  # helgemeldinger er sjeldne - ta dem bare for nyere dager
            if d.isoformat() not in done or d >= recent_cut:
                days.append(d)
        d += timedelta(days=1)
    days.sort(reverse=True)  # nyeste først: nyttigst hvis tiden går ut

    fetched_days, new_msgs, max_per_day = 0, 0, 0
    if status["probe_ok"]:
        for d in days:
            if time.time() > deadline:
                status["stopped_early"] = "tidsgrense - fortsetter neste kjøring"
                break
            js = get_json(session, LIST_URLS, {"category": "", "issuer": "", "fromDate": d.isoformat(),
                                               "toDate": d.isoformat(), "market": "", "messageTitle": ""}, status)
            msgs = extract_messages(js)
            if msgs is None:
                continue
            max_per_day = max(max_per_day, len(msgs))
            for m in msgs:
                n = norm_message(m)
                if not n["id"] or n["issuer"] not in wanted:
                    continue
                key = str(n["id"])
                if key not in rows:
                    new_msgs += 1
                    n["kind"] = classify(n["title"], n["category"])
                    rows[key] = n
            if d < recent_cut:
                done.add(d.isoformat())
            fetched_days += 1
            time.sleep(args.sleep)

    # 3) Meldingstekst for de typene modellen leser (nyeste først)
    need_body = [r for r in rows.values() if r.get("kind") in BODY_KINDS and "body" not in r]
    need_body.sort(key=lambda r: r.get("published") or "", reverse=True)
    bodies = 0
    for r in need_body:
        if time.time() > deadline:
            status["bodies_stopped_early"] = True
            break
        js = get_json(session, MSG_URLS, {"messageId": r["id"]}, status)
        if js is None:
            continue
        node = js.get("data", js) if isinstance(js, dict) else {}
        node = node.get("message", node) if isinstance(node, dict) else {}
        body = node.get("body") or node.get("text") or "" if isinstance(node, dict) else ""
        r["body"] = html_to_text(body)[:6000]
        bodies += 1
        time.sleep(args.sleep)

    save_all(rows)
    state["done_days"] = sorted(done)
    with open(state_path, "w") as f:
        json.dump(state, f)

    kinds = {}
    for r in rows.values():
        kinds[r.get("kind", "?")] = kinds.get(r.get("kind", "?"), 0) + 1
    status.update({
        "finished": datetime.now(timezone.utc).isoformat(),
        "minutes": round((time.time() - t0) / 60, 1),
        "days_planned": len(days), "days_fetched": fetched_days, "days_done_total": len(done),
        "max_messages_one_day_all_issuers": max_per_day,
        "new_messages": new_msgs, "total_messages": len(rows), "bodies_fetched": bodies,
        "bodies_missing": sum(1 for r in rows.values() if r.get("kind") in BODY_KINDS and "body" not in r),
        "by_kind": kinds,
        "issuers_with_news": len({r["issuer"] for r in rows.values()}),
    })
    with open(os.path.join(OUT_DIR, "fetch_news_status.json"), "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)
    print(json.dumps({k: v for k, v in status.items() if k != "probe_sample"}, ensure_ascii=False, indent=2))
    if not status["probe_ok"]:
        sys.exit("Newsweb-API svarte ikke - se nordnet_data/news_ml/fetch_news_status.json")


if __name__ == "__main__":
    main()
