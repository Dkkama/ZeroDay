from __future__ import annotations

import json
import re
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from config import COMPARE_FIELDS, STATE_PATH


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def seed_seq(email_id: str) -> int | None:
    m = re.fullmatch(r"email_(\d+)", str(email_id or ""))
    return int(m.group(1)) if m else None


def default_state() -> dict:
    return {
        "settings": {
            "llm_provider": "cursor",
            "imap": {
                "host": "",
                "port": 993,
                "tls": True,
                "username": "",
                "password": "",
                "folder": "INBOX",
                "poll_seconds": 0,
                "last_sync": None,
                "status": "disconnected",
            },
        },
        "emails": {},
        "audit": [],
        "jobs": [],
        "next_audit": 1,
        "next_job": 1,
    }


class Store:
    def __init__(self, path: Path = STATE_PATH):
        self.path = path
        self.lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            self.state = json.loads(path.read_text())
        else:
            self.state = default_state()
            self._write()

    def _write(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, indent=2, ensure_ascii=False))
        tmp.replace(self.path)

    def snapshot(self) -> dict:
        with self.lock:
            return deepcopy(self.state)

    def settings(self) -> dict:
        with self.lock:
            return deepcopy(self.state["settings"])

    def update_settings(self, patch: dict) -> dict:
        with self.lock:
            settings = self.state["settings"]
            if "llm_provider" in patch:
                provider = patch["llm_provider"]
                if provider not in ("cursor", "vertex"):
                    raise ValueError("llm_provider must be cursor or vertex")
                settings["llm_provider"] = provider
            if "imap" in patch and isinstance(patch["imap"], dict):
                incoming = dict(patch["imap"])
                pwd = incoming.get("password")
                if pwd in (None, "", "••••••"):
                    incoming.pop("password", None)
                if "poll_seconds" in incoming:
                    try:
                        incoming["poll_seconds"] = int(incoming["poll_seconds"] or 0)
                    except (TypeError, ValueError):
                        incoming["poll_seconds"] = 0
                settings["imap"].update({
                    k: incoming[k]
                    for k in ("host", "port", "tls", "username", "password", "folder", "poll_seconds")
                    if k in incoming
                })
            self._write()
            return deepcopy(settings)

    def set_imap_status(self, status: str, last_sync: str | None = None):
        with self.lock:
            self.state["settings"]["imap"]["status"] = status
            if last_sync is not None:
                self.state["settings"]["imap"]["last_sync"] = last_sync
            self._write()

    def upsert_email(self, rec: dict, actor: str = "program",
                     change_type: str | None = None) -> dict:
        with self.lock:
            eid = rec["email_id"]
            prev = self.state["emails"].get(eid)
            if rec.get("seq") is None:
                rec["seq"] = (prev or {}).get("seq") or seed_seq(eid) or self._next_seq_locked()
            self.state["emails"][eid] = rec
            if change_type:
                self._audit_locked(
                    email_id=eid,
                    actor=actor,
                    change_type=change_type,
                    category=rec.get("category"),
                    details={"status": rec.get("status"),
                             "defect_fields": rec.get("defect_fields"),
                             "review_reason": rec.get("review_reason")},
                )
            elif not prev:
                self._audit_locked(
                    email_id=eid,
                    actor=actor,
                    change_type=f'classified to "{_label(rec.get("category"))}"',
                    category=rec.get("category"),
                    details={"status": rec.get("status")},
                )
            self._write()
            return deepcopy(rec)

    def get_email(self, email_id: str) -> dict | None:
        with self.lock:
            rec = self.state["emails"].get(email_id)
            return deepcopy(rec) if rec else None

    def _next_seq_locked(self) -> int:
        nums = []
        for rec in self.state["emails"].values():
            if rec.get("seq") is not None:
                nums.append(int(rec["seq"]))
            else:
                derived = seed_seq(rec.get("email_id") or "")
                if derived is not None:
                    nums.append(derived)
        return (max(nums) if nums else 0) + 1

    def _ensure_seqs_locked(self) -> bool:
        changed = False
        pending = []
        for rec in self.state["emails"].values():
            if rec.get("seq") is not None:
                continue
            derived = seed_seq(rec.get("email_id") or "")
            if derived is not None:
                rec["seq"] = derived
                changed = True
            else:
                pending.append(rec)
        pending.sort(key=lambda r: (r.get("caught_at") or "", r.get("email_id") or ""))
        for rec in pending:
            rec["seq"] = self._next_seq_locked()
            changed = True
        return changed

    def all_emails(self) -> list[dict]:
        with self.lock:
            if self._ensure_seqs_locked():
                self._write()
            rows = [deepcopy(v) for v in self.state["emails"].values()]
        rows.sort(key=lambda r: r.get("seq") or 0)
        return rows

    def update_email(self, email_id: str, patch: dict, actor: str,
                     change_type: str, details: dict | None = None) -> dict:
        with self.lock:
            rec = self.state["emails"].get(email_id)
            if not rec:
                raise KeyError(email_id)
            rec.update(patch)
            rec["updated_at"] = _now()
            self._audit_locked(
                email_id=email_id,
                actor=actor,
                change_type=change_type,
                category=rec.get("category"),
                details=details or patch,
            )
            self._write()
            return deepcopy(rec)

    def audit(self, limit: int | None = None) -> list[dict]:
        with self.lock:
            rows = list(self.state["audit"])
        rows.sort(key=lambda r: r["id"], reverse=True)
        if limit:
            rows = rows[:limit]
        return rows

    def add_job(self, kind: str, provider: str, total: int) -> dict:
        with self.lock:
            job = {
                "id": self.state["next_job"],
                "kind": kind,
                "provider": provider,
                "status": "queued",
                "total": total,
                "done": 0,
                "failed": 0,
                "error": None,
                "created_at": _now(),
            }
            self.state["next_job"] += 1
            self.state["jobs"].insert(0, job)
            self._write()
            return deepcopy(job)

    def update_job(self, job_id: int, **patch) -> dict:
        with self.lock:
            for job in self.state["jobs"]:
                if job["id"] == job_id:
                    job.update(patch)
                    self._write()
                    return deepcopy(job)
        raise KeyError(job_id)

    def jobs(self) -> list[dict]:
        with self.lock:
            return deepcopy(self.state["jobs"])

    def put_file(self, email_id: str, filename: str, data: bytes) -> None:
        return None

    def get_file(self, email_id: str, filename: str) -> bytes | None:
        return None

    def reset_workspace(self):
        with self.lock:
            self.state = default_state()
            self._write()

    def _audit_locked(self, email_id, actor, change_type, category, details):
        row = {
            "id": self.state["next_audit"],
            "email_id": email_id,
            "actor": actor,
            "change_type": change_type,
            "category": category,
            "details": details or {},
            "created_at": _now(),
        }
        self.state["next_audit"] += 1
        self.state["audit"].append(row)


def _label(category: str | None) -> str:
    from config import CATEGORY_META
    if not category:
        return "unknown"
    return CATEGORY_META.get(category, {}).get("label", category)


def public_email(rec: dict, include_text: bool = False) -> dict:
    out = {k: rec.get(k) for k in (
        "email_id", "seq", "from", "subject", "body", "caught_at", "source",
        "category", "status", "review_reason", "has_defect", "defect_fields",
        "si_fields", "bl_fields", "resolved_fields", "human_validated", "fixed",
        "updated_at", "attachments",
    )}
    if not include_text:
        atts = []
        for att in rec.get("attachments") or []:
            atts.append({
                "filename": att.get("filename"),
                "ext": att.get("ext"),
                "status": att.get("status"),
                "kind": att.get("kind"),
                "notes": att.get("notes"),
                "size": att.get("size"),
            })
        out["attachments"] = atts
    out["field_view"] = []
    resolved = rec.get("resolved_fields") or {}
    si = rec.get("si_fields") or {}
    bl = rec.get("bl_fields") or {}
    from fields import field_state
    for name in COMPARE_FIELDS:
        out["field_view"].append({
            "name": name,
            **field_state(si.get(name, ""), bl.get(name, ""), resolved.get(name)),
        })
    return out
