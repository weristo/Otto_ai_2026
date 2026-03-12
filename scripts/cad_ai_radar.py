#!/usr/bin/env python3
import argparse
import datetime as dt
import html
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Dict, List


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


def http_get(url: str, headers: Dict[str, str] = None, timeout: int = 25) -> bytes:
    req = urllib.request.Request(
        url,
        headers=headers
        or {
            "User-Agent": "cad-ai-radar/1.0 (+https://github.com/weristo/Otto_ai_2026)",
            "Accept": "*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def safe_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip()


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
                "snippet": summary[:280],
            }
        )
    return out


def fetch_github_repos(query: str, per_page: int = 6) -> List[dict]:
    q = urllib.parse.quote(query)
    url = f"https://api.github.com/search/repositories?q={q}&sort=updated&order=desc&per_page={per_page}"
    raw = http_get(
        url,
        headers={
            "User-Agent": "cad-ai-radar/1.0",
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
                "snippet": safe_text(item.get("description", ""))[:280],
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
                "snippet": safe_text(h.get("story_text") or "")[:280],
                "points": h.get("points", 0),
            }
        )
    return out


def fetch_reddit(query: str, limit: int = 6) -> List[dict]:
    q = urllib.parse.quote(query)
    url = f"https://www.reddit.com/search.json?q={q}&sort=new&limit={limit}"
    raw = http_get(url, headers={"User-Agent": "cad-ai-radar/1.0 (by /u/weristo)"})
    data = json.loads(raw.decode("utf-8", errors="replace"))
    out = []
    for child in data.get("data", {}).get("children", []):
        d = child.get("data", {})
        title = safe_text(d.get("title", ""))
        permalink = d.get("permalink", "")
        out.append(
            {
                "title": title,
                "url": f"https://www.reddit.com{permalink}" if permalink else "",
                "published": dt.datetime.fromtimestamp(d.get("created_utc", 0), dt.UTC).isoformat(),
                "source": "Reddit",
                "query": query,
                "snippet": safe_text(d.get("selftext", ""))[:280],
                "score_raw": d.get("score", 0),
            }
        )
    return out


def score_item(item: dict) -> dict:
    text = f"{item.get('title','')} {item.get('snippet','')} {item.get('query','')}".lower()
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
    if item.get("source") == "GitHub":
        score += 2
        score += min(int(item.get("stars", 0)) // 200, 5)
    if item.get("source") == "arXiv":
        score += 1
    item["score"] = score
    item["flags"] = flags
    return item


def build_free_api_matrix() -> List[dict]:
    return [
        {
            "layer": "Rajz/PDF/skicc beolvasás",
            "apis": "OCR.space API (free), arXiv API (kutatás), Reddit/HN API (esettanulmányok)",
            "build_now": "PDF + kézi skicc vizuális olvasás, méret-szöveg előkinyerés, dokumentum-összefoglaló",
            "risk": "OCR minőség változó; fallback kell helyi OCR-re",
        },
        {
            "layer": "Követelményértelmezés",
            "apis": "OpenRouter free model route, LibreTranslate (self-host API)",
            "build_now": "Email szöveg + rajz adatokból gyártási brief, többnyelvű normalizálás",
            "risk": "Free model kvóták és sebesség limitált",
        },
        {
            "layer": "3D CAD/ASM generálás",
            "apis": "FreeCAD Python API (helyi), OCCT alapú toolchain",
            "build_now": "Parametrikus alkatrészgenerálás, ASM felépítés, STEP export",
            "risk": "Komplex geometriához erős szabálykészlet szükséges",
        },
        {
            "layer": "Lemezalkatrész DXF",
            "apis": "FreeCAD SheetMetal + DXF export, ezdxf (open-source)",
            "build_now": "Automatikus síkba terítés és DXF kimenet alkatrészenként",
            "risk": "Gyártói szabvány mapping szükséges (hajlítási táblák)",
        },
        {
            "layer": "SaaS + PC telepítés",
            "apis": "GitHub Actions + Resend API + Docker + REST backend",
            "build_now": "Webes multi-tenant SaaS és opcionális on-prem/PC deploy ugyanazzal a core-ral",
            "risk": "Tenant izoláció + audit + kulcskezelés kötelező",
        },
    ]


def render_html(now_local: str, top_items: List[dict], matrix: List[dict]) -> str:
    rows = []
    for i, it in enumerate(top_items, 1):
        tags = ", ".join([k for k, v in it.get("flags", {}).items() if v]) or "-"
        rows.append(
            "<tr>"
            f"<td>{i}</td>"
            f"<td><a href='{html.escape(it.get('url',''))}'>{html.escape(it.get('title',''))}</a></td>"
            f"<td>{html.escape(it.get('source',''))}</td>"
            f"<td>{html.escape(it.get('published',''))}</td>"
            f"<td>{it.get('score',0)}</td>"
            f"<td>{html.escape(tags)}</td>"
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

    return f"""
<h2>CAD AI SaaS Radar - Orankenti jelentes</h2>
<p><b>Futas:</b> {html.escape(now_local)} (Europe/Berlin)</p>
<p><b>Fokusz:</b> webes + SaaS licencelheto, opcionális PC/on-prem telepites; PDF/skicc ertelmezes, meret-kinyeres, email-kovetelmeny ertelmezes, ASM + kulon alkatresz + lemez DXF.</p>

<h3>Uj lehetosegek (ingyenes API/forras alapu radar)</h3>
<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;font-family:Arial,sans-serif;font-size:13px;">
  <thead>
    <tr><th>#</th><th>Talalat</th><th>Forras</th><th>Datum</th><th>Fit score</th><th>Cimkek</th></tr>
  </thead>
  <tbody>
    {''.join(rows) if rows else '<tr><td colspan="6">Nincs uj talalat.</td></tr>'}
  </tbody>
</table>

<h3>Mit epithetnenk ingyenes API-kbol most</h3>
<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;font-family:Arial,sans-serif;font-size:13px;">
  <thead>
    <tr><th>Reteg</th><th>Ingyenes API/komponens</th><th>Mit tudunk most megepiteni</th><th>Kockazat</th></tr>
  </thead>
  <tbody>
    {''.join(mrows)}
  </tbody>
</table>

<p><b>Kovetkezo konkret lepes:</b> Top 3 jeloltbol 2 hetes PoC: (1) PDF/skicc->meret lista, (2) email->spec parser, (3) ASM+DXF pipeline.</p>
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="cad_report_payload.json")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    items: List[dict] = []
    for q in QUERIES:
        for fn in (fetch_arxiv, fetch_github_repos, fetch_hn, fetch_reddit):
            try:
                items.extend(fn(q))
            except Exception:
                continue

    dedup = {}
    for it in items:
        u = (it.get("url") or "").strip()
        if not u:
            continue
        if u not in dedup:
            dedup[u] = score_item(it)

    ranked = sorted(dedup.values(), key=lambda x: x.get("score", 0), reverse=True)
    top = ranked[: args.limit]
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    matrix = build_free_api_matrix()
    html_body = render_html(now, top, matrix)

    payload = {
        "subject": f"CAD AI SaaS Radar - orankenti riport ({now})",
        "html": html_body,
        "meta": {"top_count": len(top), "total_seen": len(ranked)},
    }
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(json.dumps(payload["meta"], ensure_ascii=False))


if __name__ == "__main__":
    main()
