#!/usr/bin/env python3
import argparse
import datetime as dt
import html
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Dict, List, Tuple


QUERIES = [
    "AI CAD PDF dimension extraction",
    "hand sketch to CAD",
    "sheet metal DXF automation",
    "FreeCAD AI plugin",
    "on-prem CAD automation",
    "CAD SaaS API assembly generation",
]

KEYWORDS = {
    "pdf_sketch_vision": ["pdf", "drawing", "sketch", "vision", "ocr", "image"],
    "dimension_extraction": ["dimension", "measure", "extract", "tolerance"],
    "asm_generation": ["assembly", "asm", "step", "part", "bom"],
    "sheetmetal_dxf": ["sheet metal", "dxf", "flatten", "nesting"],
    "saas_web": ["saas", "web", "cloud", "api"],
    "onprem_pc": ["on-prem", "on prem", "self-host", "desktop", "windows"],
    "open_source": ["open source", "github", "oss", "apache", "mit", "gpl"],
}

SOURCE_NAMES = ("arXiv", "GitHub", "HackerNews", "Reddit")


def http_get(url: str, headers: Dict[str, str] = None, timeout: int = 25, retries: int = 2) -> bytes:
    req_headers = headers or {
        "User-Agent": "cad-ai-radar/1.1 (+https://github.com/weristo/Otto_ai_2026)",
        "Accept": "*/*",
    }
    last_error = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=req_headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(0.8 * (attempt + 1))
    raise RuntimeError(f"HTTP hiba: {last_error}")


def safe_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip()


def parse_date(value: str) -> dt.datetime | None:
    if not value:
        return None
    v = value.strip()
    formats = ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d")
    for fmt in formats:
        try:
            parsed = dt.datetime.strptime(v, fmt)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=dt.timezone.utc)
            return parsed.astimezone(dt.timezone.utc)
        except Exception:
            continue
    try:
        fixed = v.replace("Z", "+00:00")
        parsed = dt.datetime.fromisoformat(fixed)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(dt.timezone.utc)
    except Exception:
        return None


def fetch_arxiv(query: str, max_results: int = 6) -> List[dict]:
    q = urllib.parse.quote(query)
    url = (
        "https://export.arxiv.org/api/query?"
        f"search_query=all:{q}&start=0&max_results={max_results}&sortBy=submittedDate&sortOrder=descending"
    )
    raw = http_get(url)
    root = ET.fromstring(raw)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    out = []
    for entry in root.findall("atom:entry", ns):
        title = safe_text(entry.findtext("atom:title", default="", namespaces=ns))
        link = ""
        for lk in entry.findall("atom:link", ns):
            if lk.get("rel") == "alternate":
                link = lk.get("href", "")
                break
        published = safe_text(entry.findtext("atom:published", default="", namespaces=ns))
        summary = safe_text(entry.findtext("atom:summary", default="", namespaces=ns))
        out.append(
            {
                "title": title,
                "url": link,
                "published": published,
                "source": "arXiv",
                "query": query,
                "snippet": summary[:300],
            }
        )
    return out


def fetch_github_repos(query: str, per_page: int = 6) -> List[dict]:
    q = urllib.parse.quote(query)
    url = f"https://api.github.com/search/repositories?q={q}&sort=updated&order=desc&per_page={per_page}"
    raw = http_get(
        url,
        headers={
            "User-Agent": "cad-ai-radar/1.1",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    data = json.loads(raw.decode("utf-8", errors="replace"))
    out = []
    for item in data.get("items", []):
        out.append(
            {
                "title": safe_text(item.get("full_name", "")),
                "url": item.get("html_url", ""),
                "published": item.get("updated_at", ""),
                "source": "GitHub",
                "query": query,
                "snippet": safe_text(item.get("description", ""))[:300],
                "stars": item.get("stargazers_count", 0),
                "license": (item.get("license") or {}).get("spdx_id", ""),
            }
        )
    return out


def fetch_hn(query: str, limit: int = 6) -> List[dict]:
    q = urllib.parse.quote(query)
    url = f"https://hn.algolia.com/api/v1/search?query={q}&tags=story&hitsPerPage={limit}"
    raw = http_get(url)
    data = json.loads(raw.decode("utf-8", errors="replace"))
    out = []
    for h in data.get("hits", []):
        title = safe_text(h.get("title") or h.get("story_title") or "")
        link = h.get("url") or h.get("story_url") or ""
        out.append(
            {
                "title": title,
                "url": link,
                "published": h.get("created_at", ""),
                "source": "HackerNews",
                "query": query,
                "snippet": safe_text(h.get("story_text") or "")[:300],
                "points": h.get("points", 0),
            }
        )
    return out


def fetch_reddit(query: str, limit: int = 6) -> List[dict]:
    q = urllib.parse.quote(query)
    url = f"https://www.reddit.com/search.json?q={q}&sort=new&limit={limit}"
    raw = http_get(url, headers={"User-Agent": "cad-ai-radar/1.1 (by /u/weristo)"})
    data = json.loads(raw.decode("utf-8", errors="replace"))
    out = []
    for child in data.get("data", {}).get("children", []):
        d = child.get("data", {})
        title = safe_text(d.get("title", ""))
        permalink = d.get("permalink", "")
        created = dt.datetime.fromtimestamp(d.get("created_utc", 0), dt.timezone.utc).isoformat()
        out.append(
            {
                "title": title,
                "url": f"https://www.reddit.com{permalink}" if permalink else "",
                "published": created,
                "source": "Reddit",
                "query": query,
                "snippet": safe_text(d.get("selftext", ""))[:300],
                "score_raw": d.get("score", 0),
            }
        )
    return out


def score_item(item: dict, now_utc: dt.datetime) -> dict:
    text = f"{item.get('title', '')} {item.get('snippet', '')} {item.get('query', '')}".lower()
    score = 0
    flags = {}
    for tag, kws in KEYWORDS.items():
        hit = any(k in text for k in kws)
        flags[tag] = hit
        if hit:
            score += 1

    core = (
        int(flags["pdf_sketch_vision"])
        + int(flags["dimension_extraction"])
        + int(flags["asm_generation"])
        + int(flags["sheetmetal_dxf"])
    )
    score += core * 2

    source = item.get("source")
    if source == "GitHub":
        score += 2
        score += min(int(item.get("stars", 0)) // 200, 5)
    elif source == "arXiv":
        score += 1

    published = parse_date(item.get("published", ""))
    if published:
        days_old = max((now_utc - published).days, 0)
        if days_old <= 7:
            score += 3
        elif days_old <= 30:
            score += 2
        elif days_old <= 90:
            score += 1
    item["score"] = score
    item["flags"] = flags
    return item


def build_free_api_matrix() -> List[dict]:
    return [
        {
            "layer": "Rajz/PDF/skicc beolvasás",
            "apis": "OCR.space API, arXiv API, Reddit + HN API",
            "build_now": "Vizuális értelmezés, méret/szöveg előkinyerés, gyors dokumentum összefoglaló",
            "risk": "OCR minőség változó, kell fallback helyi OCR-re",
        },
        {
            "layer": "Követelményértelmezés",
            "apis": "OpenRouter free route, LibreTranslate (self-host)",
            "build_now": "Email + rajz adatokból gyártási brief és normalizált specifikáció",
            "risk": "Ingyenes modellek kvótája és késleltetése limitált",
        },
        {
            "layer": "3D CAD / ASM generálás",
            "apis": "FreeCAD Python API, OCCT toolchain",
            "build_now": "Parametrikus alkatrész, assembly felépítés, STEP export",
            "risk": "Komplex geometriához szigorú szabálykészlet kell",
        },
        {
            "layer": "Lemezalkatrész DXF",
            "apis": "FreeCAD SheetMetal + DXF export, ezdxf",
            "build_now": "Automatikus síkba terítés és DXF kimenet alkatrészenként",
            "risk": "Gyártói szabvány mapping és hajlítási táblák kellenek",
        },
        {
            "layer": "SaaS + on-prem telepítés",
            "apis": "GitHub Actions, Resend API, Docker, REST backend",
            "build_now": "Webes multi-tenant SaaS és opcionális helyi telepítés",
            "risk": "Tenant izoláció, audit és kulcskezelés kötelező",
        },
    ]


def summarize_findings(top_items: List[dict], stats: dict) -> List[str]:
    if not top_items:
        return [
            "Nem érkezett értékelhető új találat a futásban.",
            "A folyamat ettől még lefutott, forráshibák listája az alábbi táblában látható.",
        ]

    flags_count = {k: 0 for k in KEYWORDS.keys()}
    source_count = {k: 0 for k in SOURCE_NAMES}
    for item in top_items:
        source_count[item.get("source", "")] = source_count.get(item.get("source", ""), 0) + 1
        for tag, hit in item.get("flags", {}).items():
            if hit:
                flags_count[tag] += 1

    most_common_source = max(source_count.items(), key=lambda x: x[1])[0] if source_count else "n/a"
    top_tags = sorted(flags_count.items(), key=lambda x: x[1], reverse=True)[:3]
    tag_text = ", ".join([f"{k}({v})" for k, v in top_tags if v > 0]) or "nincs domináns címke"

    return [
        f"A legerősebb forrás ebben a futásban: {most_common_source}.",
        f"A top találatok fő fókusza: {tag_text}.",
        f"Forráskérések: sikeres {stats['successful_requests']} / hibás {stats['failed_requests']}.",
    ]


def build_text_summary(now_local: str, top_items: List[dict], stats: dict, insights: List[str]) -> str:
    lines = [
        "CAD AI SaaS Radar - magyar kutatási összefoglaló",
        f"Futás ideje: {now_local} (Europe/Berlin)",
        f"Lekérdezések: {stats['queries']}",
        f"Forráskérések: {stats['total_requests']} | sikeres: {stats['successful_requests']} | hibás: {stats['failed_requests']}",
        "",
        "Fő megállapítások:",
    ]
    for insight in insights:
        lines.append(f"- {insight}")

    lines.append("")
    lines.append("Top találatok:")
    if not top_items:
        lines.append("- Nincs új találat ebben a futásban.")
    else:
        for i, item in enumerate(top_items[:8], 1):
            lines.append(f"- {i}. {item.get('title', '')} | {item.get('source', '')} | score: {item.get('score', 0)}")
            lines.append(f"  {item.get('url', '')}")

    if stats["errors"]:
        lines.append("")
        lines.append("Forráshibák (első 8):")
        for err in stats["errors"][:8]:
            lines.append(f"- {err['source']} | {err['query']} | {err['error']}")

    return "\n".join(lines)


def render_html(now_local: str, top_items: List[dict], matrix: List[dict], stats: dict, insights: List[str]) -> str:
    rows = []
    for i, it in enumerate(top_items, 1):
        tags = ", ".join([k for k, v in it.get("flags", {}).items() if v]) or "-"
        rows.append(
            "<tr>"
            f"<td>{i}</td>"
            f"<td><a href='{html.escape(it.get('url', ''))}'>{html.escape(it.get('title', ''))}</a></td>"
            f"<td>{html.escape(it.get('source', ''))}</td>"
            f"<td>{html.escape(it.get('published', ''))}</td>"
            f"<td>{it.get('score', 0)}</td>"
            f"<td>{html.escape(tags)}</td>"
            "</tr>"
        )

    process_rows = []
    for source in SOURCE_NAMES:
        process_rows.append(
            "<tr>"
            f"<td>{source}</td>"
            f"<td>{stats['per_source'].get(source, {}).get('success', 0)}</td>"
            f"<td>{stats['per_source'].get(source, {}).get('errors', 0)}</td>"
            "</tr>"
        )

    error_rows = []
    for err in stats["errors"][:25]:
        error_rows.append(
            "<tr>"
            f"<td>{html.escape(err['query'])}</td>"
            f"<td>{html.escape(err['source'])}</td>"
            f"<td>{html.escape(err['error'])}</td>"
            "</tr>"
        )

    mrows = []
    for m in matrix:
        mrows.append(
            "<tr>"
            f"<td>{html.escape(m['layer'])}</td>"
            f"<td>{html.escape(m['apis'])}</td>"
            f"<td>{html.escape(m['build_now'])}</td>"
            f"<td>{html.escape(m['risk'])}</td>"
            "</tr>"
        )

    insight_list = "".join([f"<li>{html.escape(i)}</li>" for i in insights])

    return f"""
<h2>CAD AI SaaS Radar - óránkénti kutatási jelentés</h2>
<p><b>Futás ideje:</b> {html.escape(now_local)} (Europe/Berlin)</p>
<p><b>Fókusz:</b> webes SaaS + opcionális on-prem/PC, PDF/skicc értelmezés, méretkinyerés, email specifikáció, ASM + DXF pipeline.</p>

<h3>Kutatási folyamat összesítő</h3>
<p><b>Lekérdezések:</b> {stats['queries']} | <b>Összes forráskérés:</b> {stats['total_requests']} | <b>Sikeres:</b> {stats['successful_requests']} | <b>Hibás:</b> {stats['failed_requests']}</p>
<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;font-family:Arial,sans-serif;font-size:13px;">
  <thead><tr><th>Forrás</th><th>Sikeres lekérdezés</th><th>Hibás lekérdezés</th></tr></thead>
  <tbody>{''.join(process_rows)}</tbody>
</table>

<h3>Fő megállapítások</h3>
<ul>{insight_list}</ul>

<h3>Top találatok</h3>
<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;font-family:Arial,sans-serif;font-size:13px;">
  <thead>
    <tr><th>#</th><th>Találat</th><th>Forrás</th><th>Dátum</th><th>Fit score</th><th>Címkék</th></tr>
  </thead>
  <tbody>
    {''.join(rows) if rows else '<tr><td colspan="6">Nincs új találat ebben a futásban.</td></tr>'}
  </tbody>
</table>

<h3>Forráshibák (ha volt)</h3>
<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;font-family:Arial,sans-serif;font-size:12px;">
  <thead><tr><th>Lekérdezés</th><th>Forrás</th><th>Hiba</th></tr></thead>
  <tbody>
    {''.join(error_rows) if error_rows else '<tr><td colspan="3">Nincs forráshiba.</td></tr>'}
  </tbody>
</table>

<h3>Mit építhetünk most ingyenes API-kból</h3>
<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;font-family:Arial,sans-serif;font-size:13px;">
  <thead>
    <tr><th>Réteg</th><th>Ingyenes API/komponens</th><th>Most építhető</th><th>Kockázat</th></tr>
  </thead>
  <tbody>{''.join(mrows)}</tbody>
</table>
"""


def run_research(per_source_limit: int) -> Tuple[List[dict], dict]:
    items: List[dict] = []
    stats = {
        "queries": len(QUERIES),
        "total_requests": 0,
        "successful_requests": 0,
        "failed_requests": 0,
        "errors": [],
        "per_source": {s: {"success": 0, "errors": 0} for s in SOURCE_NAMES},
    }

    fetchers = [
        ("arXiv", lambda q: fetch_arxiv(q, max_results=per_source_limit)),
        ("GitHub", lambda q: fetch_github_repos(q, per_page=per_source_limit)),
        ("HackerNews", lambda q: fetch_hn(q, limit=per_source_limit)),
        ("Reddit", lambda q: fetch_reddit(q, limit=per_source_limit)),
    ]

    for query in QUERIES:
        for source, fetcher in fetchers:
            stats["total_requests"] += 1
            try:
                found = fetcher(query)
                items.extend(found)
                stats["successful_requests"] += 1
                stats["per_source"][source]["success"] += 1
            except Exception as exc:
                stats["failed_requests"] += 1
                stats["per_source"][source]["errors"] += 1
                stats["errors"].append({"query": query, "source": source, "error": safe_text(str(exc))[:180]})
    return items, stats


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="cad_report_payload.json")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--per-source-limit", type=int, default=6)
    args = parser.parse_args()

    raw_items, stats = run_research(per_source_limit=args.per_source_limit)

    dedup = {}
    now_utc = dt.datetime.now(dt.timezone.utc)
    for it in raw_items:
        u = (it.get("url") or "").strip()
        if not u:
            continue
        if u not in dedup:
            dedup[u] = score_item(it, now_utc=now_utc)

    ranked = sorted(dedup.values(), key=lambda x: x.get("score", 0), reverse=True)
    top = ranked[: args.limit]
    now_local = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    matrix = build_free_api_matrix()
    insights = summarize_findings(top, stats)
    html_body = render_html(now_local, top, matrix, stats, insights)
    text_body = build_text_summary(now_local, top, stats, insights)

    payload = {
        "subject": f"CAD AI SaaS Radar - magyar kutatási riport ({now_local})",
        "html": html_body,
        "text": text_body,
        "meta": {
            "top_count": len(top),
            "total_seen": len(ranked),
            "total_requests": stats["total_requests"],
            "successful_requests": stats["successful_requests"],
            "failed_requests": stats["failed_requests"],
        },
    }
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(json.dumps(payload["meta"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
