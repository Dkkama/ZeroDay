from __future__ import annotations

import email as email_lib
import imaplib
import json
import zipfile
from datetime import datetime, timezone
from email.header import decode_header
from pathlib import Path

from config import UPLOAD_DIR
from seed import build_record


def ingest_zip(data: bytes, name: str = "upload.zip") -> tuple[Path, list[dict]]:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    dest = UPLOAD_DIR / f"{stamp}_{Path(name).stem}"
    dest.mkdir(parents=True, exist_ok=True)
    zpath = dest / "bundle.zip"
    zpath.write_bytes(data)
    with zipfile.ZipFile(zpath) as zf:
        zf.extractall(dest)
    root = _find_inbox_root(dest)
    emails = []
    for path in sorted((root / "inbox").glob("*.json")):
        emails.append(json.loads(path.read_text()))
    return root, emails


def _find_inbox_root(dest: Path) -> Path:
    if (dest / "inbox").is_dir():
        return dest
    for child in dest.rglob("inbox"):
        if child.is_dir():
            return child.parent
    raise FileNotFoundError("zip has no inbox/ folder")


def decode_mime(value) -> str:
    if not value:
        return ""
    parts = decode_header(value)
    out = []
    for chunk, enc in parts:
        if isinstance(chunk, bytes):
            out.append(chunk.decode(enc or "utf-8", errors="replace"))
        else:
            out.append(chunk)
    return "".join(out)


def fetch_imap(cfg: dict, limit: int = 20) -> tuple[Path, list[dict]]:
    host = (cfg.get("host") or "").strip()
    if not host:
        raise ValueError("IMAP host is required")
    port = int(cfg.get("port") or 993)
    user = cfg.get("username") or ""
    password = cfg.get("password") or ""
    folder = cfg.get("folder") or "INBOX"
    tls = bool(cfg.get("tls", True))

    mailbox = imaplib.IMAP4_SSL(host, port) if tls else imaplib.IMAP4(host, port)
    mailbox.login(user, password)
    mailbox.select(folder)
    _, data = mailbox.search(None, "ALL")
    ids = (data[0] or b"").split()
    ids = ids[-limit:]

    dest = UPLOAD_DIR / f"imap_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    inbox_dir = dest / "inbox"
    att_dir = dest / "attachments"
    inbox_dir.mkdir(parents=True)
    att_dir.mkdir(parents=True)

    emails = []
    for i, msg_id in enumerate(ids, 1):
        _, msg_data = mailbox.fetch(msg_id, "(RFC822)")
        raw = msg_data[0][1]
        msg = email_lib.message_from_bytes(raw)
        eid = f"imap_{msg_id.decode() if isinstance(msg_id, bytes) else msg_id}"
        attachments = []
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                disp = str(part.get_content_disposition() or "")
                filename = part.get_filename()
                if filename:
                    filename = decode_mime(filename)
                    safe = f"{eid}_{filename}"
                    (att_dir / safe).write_bytes(part.get_payload(decode=True) or b"")
                    attachments.append(f"attachments/{safe}")
                elif part.get_content_type() == "text/plain" and not body:
                    payload = part.get_payload(decode=True) or b""
                    body = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        else:
            payload = msg.get_payload(decode=True) or b""
            body = payload.decode(msg.get_content_charset() or "utf-8", errors="replace")

        rec = {
            "email_id": eid,
            "from": decode_mime(msg.get("From")),
            "subject": decode_mime(msg.get("Subject")),
            "body": body,
            "attachments": attachments,
        }
        (inbox_dir / f"{eid}.json").write_text(json.dumps(rec, indent=2))
        emails.append(rec)
    mailbox.logout()
    return dest, emails


def records_from_ingest(root: Path, emails: list[dict], source: str) -> list[dict]:
    out = []
    for email in emails:
        out.append(build_record(email, {}, root, source=source))
    return out
