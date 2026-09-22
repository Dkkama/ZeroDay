from __future__ import annotations

import threading
import time
from copy import deepcopy

from google.cloud import firestore

from config import GCP_PROJECT
from store import Store, _label, _now, default_state, seed_seq


def _clean(value):
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


class FirestoreStore:
    """Same desk operations as the JSON store, one document per email, job, and audit row."""

    def __init__(self, project: str = GCP_PROJECT):
        self.db = firestore.Client(project=project)
        self.lock = threading.Lock()
        self.emails = self.db.collection("emails")
        self.audit_col = self.db.collection("audit")
        self.jobs_col = self.db.collection("jobs")
        self.files = self.db.collection("files")
        self.settings_ref = self.db.collection("settings").document("app")
        self.meta_ref = self.db.collection("meta").document("counters")
        if not self.settings_ref.get().exists:
            state = default_state()
            self.settings_ref.set(_clean(state["settings"]))
            self.meta_ref.set({"next_audit": 1, "next_job": 1})

    def settings(self) -> dict:
        data = self.settings_ref.get().to_dict() or default_state()["settings"]
        return deepcopy(data)

    def update_settings(self, patch: dict) -> dict:
        with self.lock:
            settings = self.settings()
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
                settings.setdefault("imap", {})
                settings["imap"].update({
                    k: incoming[k]
                    for k in ("host", "port", "tls", "username", "password", "folder", "poll_seconds")
                    if k in incoming
                })
            if "auto_seed" in patch:
                settings["auto_seed"] = bool(patch["auto_seed"])
            self.settings_ref.set(_clean(settings))
            return deepcopy(settings)

    def set_imap_status(self, status: str, last_sync: str | None = None):
        with self.lock:
            settings = self.settings()
            settings.setdefault("imap", {})
            settings["imap"]["status"] = status
            if last_sync is not None:
                settings["imap"]["last_sync"] = last_sync
            self.settings_ref.set(_clean(settings))

    def upsert_email(self, rec: dict, actor: str = "program",
                     change_type: str | None = None) -> dict:
        with self.lock:
            eid = rec["email_id"]
            prev_snap = self.emails.document(eid).get()
            prev = prev_snap.to_dict() if prev_snap.exists else None
            if rec.get("seq") is None:
                rec["seq"] = (prev or {}).get("seq") or seed_seq(eid) or self._next_seq()
            self.emails.document(eid).set(_clean(rec))
            if change_type:
                self._audit(eid, actor, change_type, rec.get("category"), {
                    "status": rec.get("status"),
                    "defect_fields": rec.get("defect_fields"),
                    "review_reason": rec.get("review_reason"),
                })
            elif not prev:
                self._audit(
                    eid, actor,
                    f'classified to "{_label(rec.get("category"))}"',
                    rec.get("category"),
                    {"status": rec.get("status")},
                )
            return deepcopy(rec)

    def get_email(self, email_id: str) -> dict | None:
        snap = self.emails.document(email_id).get()
        return snap.to_dict() if snap.exists else None

    def _next_seq(self) -> int:
        nums = []
        for snap in self.emails.select(["seq", "email_id"]).stream():
            rec = snap.to_dict() or {}
            if rec.get("seq") is not None:
                nums.append(int(rec["seq"]))
            else:
                derived = seed_seq(rec.get("email_id") or snap.id)
                if derived is not None:
                    nums.append(derived)
        return (max(nums) if nums else 0) + 1

    def all_emails(self) -> list[dict]:
        rows = [snap.to_dict() for snap in self.emails.stream()]
        rows.sort(key=lambda r: r.get("seq") or 0)
        return rows

    def update_email(self, email_id: str, patch: dict, actor: str,
                     change_type: str, details: dict | None = None) -> dict:
        with self.lock:
            snap = self.emails.document(email_id).get()
            if not snap.exists:
                raise KeyError(email_id)
            rec = snap.to_dict()
            rec.update(patch)
            rec["updated_at"] = _now()
            self.emails.document(email_id).set(_clean(rec))
            self._audit(email_id, actor, change_type, rec.get("category"), details or patch)
            return deepcopy(rec)

    def audit(self, limit: int | None = None) -> list[dict]:
        query = self.audit_col.order_by("id", direction=firestore.Query.DESCENDING)
        if limit:
            query = query.limit(limit)
        return [snap.to_dict() for snap in query.stream()]

    def add_job(self, kind: str, provider: str, total: int) -> dict:
        with self.lock:
            job_id = self._take_counter("next_job")
            job = {
                "id": job_id,
                "kind": kind,
                "provider": provider,
                "status": "queued",
                "total": total,
                "done": 0,
                "failed": 0,
                "error": None,
                "created_at": _now(),
            }
            self.jobs_col.document(str(job_id)).set(job)
            return deepcopy(job)

    def update_job(self, job_id: int, **patch) -> dict:
        with self.lock:
            ref = self.jobs_col.document(str(job_id))
            snap = ref.get()
            if not snap.exists:
                raise KeyError(job_id)
            job = snap.to_dict()
            job.update(patch)
            ref.set(_clean(job))
            return deepcopy(job)

    def jobs(self) -> list[dict]:
        rows = [snap.to_dict() for snap in self.jobs_col.stream()]
        rows.sort(key=lambda r: r.get("id") or 0, reverse=True)
        return rows

    def put_file(self, email_id: str, filename: str, data: bytes) -> None:
        self.files.document(f"{email_id}__{filename}").set({
            "email_id": email_id,
            "filename": filename,
            "data": data,
        })

    def get_file(self, email_id: str, filename: str) -> bytes | None:
        snap = self.files.document(f"{email_id}__{filename}").get()
        if not snap.exists:
            return None
        data = (snap.to_dict() or {}).get("data")
        if isinstance(data, str):
            return data.encode("utf-8")
        return data or None

    def reset_workspace(self):
        with self.lock:
            self._wipe(self.emails)
            self._wipe(self.audit_col)
            self._wipe(self.jobs_col)
            self._wipe(self.files)
            state = default_state()
            self.settings_ref.set(_clean(state["settings"]))
            self.meta_ref.set({"next_audit": 1, "next_job": 1})

    def import_state(self, state: dict) -> dict:
        """Copy a JSON store snapshot in once. Used to move the local inbox across."""
        with self.lock:
            self._wipe(self.emails)
            self._wipe(self.audit_col)
            self._wipe(self.jobs_col)
            settings = state.get("settings") or default_state()["settings"]
            self.settings_ref.set(_clean(settings))
            emails = list((state.get("emails") or {}).values())
            audit = list(state.get("audit") or [])
            jobs = list(state.get("jobs") or [])
            self._put_all(self.emails, ((rec["email_id"], rec) for rec in emails))
            self._put_all(self.audit_col, ((str(row["id"]), row) for row in audit))
            self._put_all(self.jobs_col, ((str(job["id"]), job) for job in jobs))
            next_audit = int(state.get("next_audit") or (max((r["id"] for r in audit), default=0) + 1))
            next_job = int(state.get("next_job") or (max((j["id"] for j in jobs), default=0) + 1))
            self.meta_ref.set({"next_audit": next_audit, "next_job": next_job})
            return {"emails": len(emails), "audit": len(audit), "jobs": len(jobs)}

    def _take_counter(self, name: str) -> int:
        last = None
        for attempt in range(8):
            transaction = self.db.transaction()

            @firestore.transactional
            def bump(transaction):
                snap = self.meta_ref.get(transaction=transaction)
                data = snap.to_dict() or {"next_audit": 1, "next_job": 1}
                current = int(data.get(name) or 1)
                data[name] = current + 1
                transaction.set(self.meta_ref, data, merge=True)
                return current

            try:
                return bump(transaction)
            except Exception as exc:
                last = exc
                text = str(exc)
                if "contention" not in text and "Failed to commit" not in text and "Aborted" not in text:
                    raise
                time.sleep(0.05 * (2 ** attempt))
        raise last

    def _audit(self, email_id, actor, change_type, category, details):
        row_id = self._take_counter("next_audit")
        row = {
            "id": row_id,
            "email_id": email_id,
            "actor": actor,
            "change_type": change_type,
            "category": category,
            "details": details or {},
            "created_at": _now(),
        }
        self.audit_col.document(str(row_id)).set(_clean(row))

    def _put_all(self, collection, pairs):
        batch = self.db.batch()
        count = 0
        for doc_id, payload in pairs:
            batch.set(collection.document(str(doc_id)), _clean(payload))
            count += 1
            if count == 400:
                batch.commit()
                batch = self.db.batch()
                count = 0
        if count:
            batch.commit()

    def _wipe(self, collection):
        while True:
            docs = list(collection.limit(400).stream())
            if not docs:
                return
            batch = self.db.batch()
            for snap in docs:
                batch.delete(snap.reference)
            batch.commit()


def open_store():
    from config import STORE_BACKEND
    if STORE_BACKEND == "firestore":
        return FirestoreStore()
    return Store()
