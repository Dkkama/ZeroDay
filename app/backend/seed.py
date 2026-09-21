from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config import DATA_V2, FLASH_SCORE, FLASH_SUBMISSION, ROOT
from fields import empty_fields, extract_fields
from store import Store

sys.path.insert(0, str(ROOT / "sdoc_eval"))
from extract import extract_attachment  # noqa: E402


def load_flash_score() -> dict:
    if FLASH_SCORE.exists():
        return json.loads(FLASH_SCORE.read_text())
    return {}


def attachment_kind(filename: str) -> str:
    name = filename.upper()
    if "_SI." in name or name.endswith("_SI") or "SI." in Path(filename).name.upper():
        return "si"
    if "_BL." in name or name.endswith("_BL"):
        return "bl"
    return "other"


def load_attachment(root: Path, rel: str) -> dict:
    path = root / rel
    data = path.read_bytes() if path.exists() else b""
    rec = extract_attachment(path.name, data)
    rec["kind"] = attachment_kind(path.name)
    rec["rel"] = rel
    rec["abs"] = str(path) if path.exists() else ""
    rec["size"] = len(data)
    rec.pop("images", None)
    return rec


def build_record(email: dict, decision: dict, root: Path, source: str = "seed") -> dict:
    atts = [load_attachment(root, rel) for rel in email.get("attachments") or []]
    si_text = next((a.get("text") or "" for a in atts if a.get("kind") == "si"), "")
    bl_text = next((a.get("text") or "" for a in atts if a.get("kind") == "bl"), "")
    if not si_text:
        texts = [a.get("text") or "" for a in atts]
        si_text = texts[0] if texts else ""
    if not bl_text:
        texts = [a.get("text") or "" for a in atts]
        bl_text = texts[1] if len(texts) > 1 else ""
    n = int((email.get("email_id") or "email_0").split("_")[-1] or 0)
    caught = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(hours=n)
    return {
        "email_id": email["email_id"],
        "from": email.get("from") or "",
        "subject": email.get("subject") or "",
        "body": email.get("body") or "",
        "caught_at": caught.isoformat(),
        "source": source,
        "category": decision.get("category") or "GENERAL",
        "status": decision.get("status") or "OK",
        "review_reason": decision.get("review_reason"),
        "has_defect": bool(decision.get("has_defect")),
        "defect_fields": list(decision.get("defect_fields") or []),
        "si_fields": extract_fields(si_text) if si_text else empty_fields(),
        "bl_fields": extract_fields(bl_text) if bl_text else empty_fields(),
        "resolved_fields": {},
        "human_validated": False,
        "updated_at": caught.isoformat(),
        "attachments": atts,
        "root": str(root),
    }


LIVE_EMAIL_ID = "live_001"
LIVE_SOURCE_EMAIL = "email_004"


def next_live_id(store: Store) -> str:
    n = 1
    while store.get_email(f"live_{n:03d}"):
        n += 1
    return f"live_{n:03d}"


def load_one_attached(store: Store, email_id: str | None = None) -> dict:
    email_id = email_id or next_live_id(store)
    path = DATA_V2 / "inbox" / f"{LIVE_SOURCE_EMAIL}.json"
    if not path.exists():
        raise FileNotFoundError(f"sample {LIVE_SOURCE_EMAIL} missing at {path}")
    email = json.loads(path.read_text())
    email["email_id"] = email_id
    rec = build_record(email, {}, DATA_V2, source="upload")
    rec["email_id"] = email_id
    rec["processed_live"] = False
    store.upsert_email(rec, actor="program", change_type="loaded one email with attachments")
    return rec


def seed_sample(store: Store, replace: bool = True) -> int:
    inbox_dir = DATA_V2 / "inbox"
    if not inbox_dir.exists():
        raise FileNotFoundError(f"sample inbox missing: {inbox_dir}")
    decisions = {}
    if FLASH_SUBMISSION.exists():
        decisions = json.loads(FLASH_SUBMISSION.read_text())
    if replace:
        store.reset_workspace()
    count = 0
    for path in sorted(inbox_dir.glob("email_*.json")):
        email = json.loads(path.read_text())
        eid = email["email_id"]
        rec = build_record(email, decisions.get(eid) or {}, DATA_V2, source="seed")
        store.upsert_email(rec, actor="program")
        count += 1
    return count
