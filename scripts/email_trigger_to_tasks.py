#!/usr/bin/env python3
import email
import imaplib
import json
import os
import re
import ssl
import sys
import urllib.request
from email.header import decode_header
from email.utils import parsedate_to_datetime


TRIGGER_PATTERNS = [
    r"\boksa\b",
    r"\bjó funkció\b",
    r"\bjo funkcio\b",
    r"\bvedd fel fejleszt[ée]si tervbe\b",
    r"\bfejleszt[ée]si tervbe\b",
    r"\bbacklog\b",
    r"\bfeature request\b",
]


def decode_mime(value: str) -> str:
    if not value:
        return ""
    out = []
    for part, enc in decode_header(value):
        if isinstance(part, bytes):
            out.append(part.decode(enc or "utf-8", errors="replace"))
        else:
            out.append(part)
    return "".join(out).strip()


def strip_html(raw: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", raw or "")
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def get_text_from_msg(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition", ""))
            if "attachment" in disp.lower():
                continue
            if ctype == "text/plain":
                payload = part.get_payload(decode=True) or b""
                charset = part.get_content_charset() or "utf-8"
                return payload.decode(charset, errors="replace").strip()
            if ctype == "text/html":
                payload = part.get_payload(decode=True) or b""
                charset = part.get_content_charset() or "utf-8"
                return strip_html(payload.decode(charset, errors="replace"))
        return ""
    payload = msg.get_payload(decode=True) or b""
    charset = msg.get_content_charset() or "utf-8"
    raw = payload.decode(charset, errors="replace")
    if msg.get_content_type() == "text/html":
        return strip_html(raw)
    return raw.strip()


def contains_trigger(subject: str, body: str) -> bool:
    hay = f"{subject}\n{body}".lower()
    return any(re.search(p, hay, flags=re.IGNORECASE) for p in TRIGGER_PATTERNS)


def api_post(url: str, payload: dict, master_key: str) -> dict:
    raw = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=raw,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "x-master-key": master_key,
            "User-Agent": "weristo-email-trigger/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def api_get(url: str, master_key: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={"x-master-key": master_key, "User-Agent": "weristo-email-trigger/1.0"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def main():
    if "--self-test" in sys.argv:
        sample = "oksa ez egy jo funkcio lenne nekunk, vedd fel fejlesztesi tervbe"
        print("SELFTEST_TRIGGER", contains_trigger("teszt", sample))
        return 0

    imap_host = os.getenv("GMAIL_IMAP_HOST", "imap.gmail.com")
    imap_user = os.getenv("GMAIL_IMAP_USER", "").strip()
    imap_pass = os.getenv("GMAIL_IMAP_APP_PASSWORD", "").strip()
    from_filter = os.getenv("TRIGGER_FROM_FILTER", "ottolokos@gmail.com").strip().lower()
    api_base = os.getenv("WERISTO_API_BASE", "https://weristo.de").rstrip("/")
    master_key = os.getenv("WERISTO_MASTER_KEY", "").strip()
    max_scan = int(os.getenv("TRIGGER_SCAN_LIMIT", "25"))

    if not imap_user or not imap_pass or not master_key:
        print("SKIP: missing required env (GMAIL_IMAP_USER / GMAIL_IMAP_APP_PASSWORD / WERISTO_MASTER_KEY)")
        return 0

    tasks_data = api_get(f"{api_base}/api/master/tasks", master_key)
    tasks_text = (tasks_data.get("content") or "") if isinstance(tasks_data, dict) else ""

    ctx = ssl.create_default_context()
    imap = imaplib.IMAP4_SSL(imap_host, 993, ssl_context=ctx)
    imap.login(imap_user, imap_pass)
    imap.select("INBOX")
    status, data = imap.search(None, "ALL")
    if status != "OK":
        print("IMAP search failed")
        imap.logout()
        return 1

    ids = data[0].split()
    ids = ids[-max_scan:]
    created = 0
    scanned = 0

    for mid in reversed(ids):
        st, msg_data = imap.fetch(mid, "(RFC822)")
        if st != "OK" or not msg_data or not msg_data[0]:
            continue
        raw = msg_data[0][1]
        msg = email.message_from_bytes(raw)
        scanned += 1

        frm = decode_mime(msg.get("From", ""))
        subject = decode_mime(msg.get("Subject", ""))
        msgid = decode_mime(msg.get("Message-Id", "")) or f"imap-id:{mid.decode(errors='ignore')}"
        date_raw = decode_mime(msg.get("Date", ""))
        try:
            dt_txt = parsedate_to_datetime(date_raw).isoformat()
        except Exception:
            dt_txt = date_raw

        if from_filter and from_filter not in frm.lower():
            continue

        body = get_text_from_msg(msg)
        if not contains_trigger(subject, body):
            continue

        marker = f"[email-msgid:{msgid}]"
        if marker in tasks_text:
            continue

        snippet = re.sub(r"\s+", " ", body or "").strip()[:240]
        task = (
            f"{marker} Email-triggerelt fejlesztési ötlet: "
            f"\"{subject or 'nincs tárgy'}\" | feladó: {frm} | dátum: {dt_txt} | kivonat: {snippet}"
        )
        res = api_post(
            f"{api_base}/api/master/tasks/add",
            {"task": task, "priority": "medium", "section": "next"},
            master_key,
        )
        if res.get("success"):
            created += 1
            tasks_text += "\n" + marker

    imap.logout()
    print(json.dumps({"scanned": scanned, "created_tasks": created}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
