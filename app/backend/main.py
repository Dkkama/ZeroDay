from __future__ import annotations

import hashlib
import hmac
import json
import threading
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import (
    CATEGORY_META,
    COMPARE_FIELDS,
    DEMO_EMAIL,
    DEMO_PASSWORD,
    FLASH_SCORE,
    SESSION_SECRET,
    UPLOAD_DIR,
)
from exports import (
    audit_to_csv,
    audit_to_pdf,
    filter_emails,
    preset_spec,
    results_rows,
    submission_payload,
    to_csv,
    to_json,
    to_xlsx,
)
from ingest import fetch_imap, ingest_zip
from llm import classify, guard_vertex_batch
from seed import load_attachment, load_flash_score, seed_sample
from store import Store, public_email

store = Store()
app = FastAPI(title="ZeroDay SDOC", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoginBody(BaseModel):
    email: str
    password: str


class SettingsBody(BaseModel):
    llm_provider: Optional[str] = None
    imap: Optional[dict] = None


class FieldEdit(BaseModel):
    name: str
    source: Optional[str] = None
    value: Optional[str] = None


class ProcessBody(BaseModel):
    email_ids: Optional[list[str]] = None
    all_unprocessed: bool = False


def _token() -> str:
    return hmac.new(SESSION_SECRET.encode(), DEMO_EMAIL.encode(), hashlib.sha256).hexdigest()


def require_auth(authorization: Optional[str]):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "sign in required")
    if not hmac.compare_digest(authorization.split(" ", 1)[1], _token()):
        raise HTTPException(401, "invalid session")


@app.post("/api/login")
def login(body: LoginBody):
    if body.email.strip().lower() != DEMO_EMAIL.lower() or body.password != DEMO_PASSWORD:
        raise HTTPException(401, "unknown clerk")
    return {"token": _token(), "email": DEMO_EMAIL, "name": "Clerk"}


@app.get("/api/me")
def me(authorization: Optional[str] = Header(None)):
    require_auth(authorization)
    return {"email": DEMO_EMAIL, "name": "Clerk"}


@app.get("/api/meta")
def meta(authorization: Optional[str] = Header(None)):
    require_auth(authorization)
    score = load_flash_score()
    final = None
    try:
        final = score.get("full", {}).get("final_score")
    except Exception:
        final = None
    return {
        "categories": CATEGORY_META,
        "fields": COMPARE_FIELDS,
        "demo_score": final,
        "score_path": str(FLASH_SCORE),
    }


@app.post("/api/seed")
def seed(authorization: Optional[str] = Header(None)):
    require_auth(authorization)
    n = seed_sample(store, replace=True)
    return {"loaded": n}


@app.get("/api/settings")
def get_settings(authorization: Optional[str] = Header(None)):
    require_auth(authorization)
    settings = store.settings()
    imap = dict(settings.get("imap") or {})
    if imap.get("password"):
        imap["password"] = "••••••"
    settings["imap"] = imap
    return settings


@app.put("/api/settings")
def put_settings(body: SettingsBody, authorization: Optional[str] = Header(None)):
    require_auth(authorization)
    return store.update_settings(body.model_dump(exclude_none=True))


_seed_lock = threading.Lock()


def ensure_seed():
    if store.all_emails():
        return
    with _seed_lock:
        if store.all_emails():
            return
        seed_sample(store, replace=False)


@app.get("/api/stats")
def stats(authorization: Optional[str] = Header(None)):
    require_auth(authorization)
    ensure_seed()
    rows = store.all_emails()
    by_cat = {k: 0 for k in CATEGORY_META}
    by_status = {"OK": 0, "MISMATCH": 0, "NEEDS_REVIEW": 0}
    reasons = {}
    for rec in rows:
        by_cat[rec.get("category") or "GENERAL"] = by_cat.get(rec.get("category") or "GENERAL", 0) + 1
        by_status[rec.get("status") or "OK"] = by_status.get(rec.get("status") or "OK", 0) + 1
        if rec.get("review_reason"):
            reasons[rec["review_reason"]] = reasons.get(rec["review_reason"], 0) + 1
    queue = [r for r in rows if r.get("category") == "BL_COMPARISON"
             and r.get("status") in ("NEEDS_REVIEW", "MISMATCH")
             and not r.get("human_validated")]
    return {
        "total": len(rows),
        "by_category": by_cat,
        "by_status": by_status,
        "review_reasons": reasons,
        "check_documents": by_cat.get("BL_COMPARISON", 0),
        "needs_human": len(queue),
    }


@app.get("/api/emails")
def list_emails(
    authorization: Optional[str] = Header(None),
    category: Optional[str] = None,
    status: Optional[str] = None,
    q: Optional[str] = None,
    queue: bool = False,
):
    require_auth(authorization)
    ensure_seed()
    rows = store.all_emails()
    if queue:
        rows = [r for r in rows
                if r.get("category") == "BL_COMPARISON"
                and r.get("status") in ("NEEDS_REVIEW", "MISMATCH")
                and not r.get("human_validated")]
        rows.sort(key=lambda r: (0 if r.get("status") == "NEEDS_REVIEW" else 1, r.get("email_id")))
    if category:
        rows = [r for r in rows if r.get("category") == category]
    if status:
        rows = [r for r in rows if r.get("status") == status]
    if q:
        needle = q.lower()
        rows = [r for r in rows
                if needle in (r.get("subject") or "").lower()
                or needle in (r.get("email_id") or "").lower()
                or needle in (r.get("from") or "").lower()]
    return [public_email(r) for r in rows]


@app.get("/api/emails/{email_id}")
def get_email(email_id: str, authorization: Optional[str] = Header(None)):
    require_auth(authorization)
    rec = store.get_email(email_id)
    if not rec:
        raise HTTPException(404, "email not found")
    return public_email(rec, include_text=True)


@app.get("/api/emails/{email_id}/attachments/{filename}")
def get_attachment(email_id: str, filename: str,
                   authorization: Optional[str] = Header(None)):
    require_auth(authorization)
    rec = store.get_email(email_id)
    if not rec:
        raise HTTPException(404, "email not found")
    for att in rec.get("attachments") or []:
        if att.get("filename") == filename:
            path = Path(att.get("abs") or "")
            if path.exists():
                return FileResponse(path, filename=filename)
            text = att.get("text") or ""
            return Response(text.encode("utf-8"), media_type="text/plain")
    raise HTTPException(404, "attachment not found")


@app.post("/api/emails/{email_id}/validate")
def validate(email_id: str, authorization: Optional[str] = Header(None)):
    require_auth(authorization)
    rec = store.update_email(
        email_id,
        {"human_validated": True},
        actor="human",
        change_type="validated BL / resolved fields",
        details={"human_validated": True},
    )
    return public_email(rec)


@app.post("/api/emails/{email_id}/fields")
def edit_fields(email_id: str, body: list[FieldEdit],
                authorization: Optional[str] = Header(None)):
    require_auth(authorization)
    rec = store.get_email(email_id)
    if not rec:
        raise HTTPException(404, "email not found")
    resolved = dict(rec.get("resolved_fields") or {})
    changed = []
    si = rec.get("si_fields") or {}
    bl = rec.get("bl_fields") or {}
    for item in body:
        name = item.name
        if name not in COMPARE_FIELDS:
            continue
        if item.source == "si":
            value = si.get(name) or ""
        elif item.source == "bl":
            value = bl.get(name) or ""
        else:
            value = item.value or ""
        resolved[name] = value
        changed.append({"field": name, "source": item.source, "value": value})
    rec = store.update_email(
        email_id,
        {"resolved_fields": resolved, "human_validated": False},
        actor="human",
        change_type="edited fields: " + ", ".join(c["field"] for c in changed),
        details={"fields": changed},
    )
    return public_email(rec)


@app.get("/api/audit")
def audit(authorization: Optional[str] = Header(None), limit: int = 500):
    require_auth(authorization)
    return store.audit(limit=limit)


@app.get("/api/jobs")
def jobs(authorization: Optional[str] = Header(None)):
    require_auth(authorization)
    return store.jobs()


@app.post("/api/ingest/sample")
def ingest_sample(authorization: Optional[str] = Header(None)):
    require_auth(authorization)
    n = seed_sample(store, replace=True)
    return {"loaded": n, "source": "sample"}


@app.post("/api/ingest/upload")
def ingest_upload(file: UploadFile = File(...),
                  authorization: Optional[str] = Header(None)):
    require_auth(authorization)
    data = file.file.read()
    root, emails = ingest_zip(data, file.filename or "upload.zip")
    provider = store.settings()["llm_provider"]
    job = store.add_job("upload", provider, len(emails))
    threading.Thread(target=_run_ingest, args=(job["id"], root, emails, "upload", provider),
                     daemon=True).start()
    return {"job": job, "count": len(emails)}


class ImapBody(BaseModel):
    limit: int = 15


@app.post("/api/ingest/imap/test")
def imap_test(authorization: Optional[str] = Header(None)):
    require_auth(authorization)
    cfg = store.settings()["imap"]
    try:
        fetch_imap(cfg, limit=1)
        store.set_imap_status("connected")
        return {"ok": True}
    except Exception as exc:
        store.set_imap_status("error")
        raise HTTPException(400, str(exc))


@app.post("/api/ingest/imap/fetch")
def imap_fetch(body: ImapBody, authorization: Optional[str] = Header(None)):
    require_auth(authorization)
    cfg = store.settings()["imap"]
    try:
        root, emails = fetch_imap(cfg, limit=body.limit)
    except Exception as exc:
        store.set_imap_status("error")
        raise HTTPException(400, str(exc))
    provider = store.settings()["llm_provider"]
    job = store.add_job("imap", provider, len(emails))
    from datetime import datetime, timezone
    store.set_imap_status("connected", datetime.now(timezone.utc).isoformat())
    threading.Thread(target=_run_ingest, args=(job["id"], root, emails, "imap", provider),
                     daemon=True).start()
    return {"job": job, "count": len(emails)}


@app.post("/api/process")
def process(body: ProcessBody, authorization: Optional[str] = Header(None)):
    require_auth(authorization)
    provider = store.settings()["llm_provider"]
    if body.email_ids:
        ids = body.email_ids
    elif body.all_unprocessed:
        ids = [r["email_id"] for r in store.all_emails() if r.get("source") != "seed"
               and r.get("category") == "GENERAL" and not r.get("subject")]
        ids = [r["email_id"] for r in store.all_emails() if r.get("source") in ("upload", "imap")]
    else:
        raise HTTPException(400, "email_ids required")
    try:
        guard_vertex_batch(provider, len(ids))
    except RuntimeError as exc:
        raise HTTPException(400, str(exc))
    job = store.add_job("process", provider, len(ids))
    threading.Thread(target=_run_process, args=(job["id"], ids, provider), daemon=True).start()
    return {"job": job}


@app.post("/api/jobs/{job_id}/retry")
def retry_job(job_id: int, authorization: Optional[str] = Header(None)):
    require_auth(authorization)
    provider = store.settings()["llm_provider"]
    failed_ids = []
    # retry last failed process by re-running all upload/imap emails without defects? 
    # simpler: re-run the same kind is not stored. Retry means process all non-seed pending.
    ids = [r["email_id"] for r in store.all_emails()
           if r.get("source") in ("upload", "imap") and not r.get("processed_live")]
    if not ids:
        ids = [r["email_id"] for r in store.all_emails() if r.get("source") in ("upload", "imap")]
    try:
        guard_vertex_batch(provider, len(ids))
    except RuntimeError as exc:
        raise HTTPException(400, str(exc))
    job = store.add_job("retry", provider, len(ids))
    threading.Thread(target=_run_process, args=(job["id"], ids, provider), daemon=True).start()
    return {"job": job}


@app.get("/api/export/results")
def export_results(
    authorization: Optional[str] = Header(None),
    fmt: str = "json",
    preset: Optional[str] = None,
    statuses: Optional[str] = None,
    categories: Optional[str] = None,
    human_validated: Optional[bool] = None,
):
    require_auth(authorization)
    spec = preset_spec(preset) if preset else {}
    if statuses:
        spec["statuses"] = [s.strip() for s in statuses.split(",") if s.strip()]
    if categories:
        spec["categories"] = [s.strip() for s in categories.split(",") if s.strip()]
    if human_validated is not None:
        spec["human_validated"] = human_validated
    rows = results_rows(filter_emails(store.all_emails(), spec))
    if fmt == "csv":
        return Response(to_csv(rows), media_type="text/csv",
                        headers={"Content-Disposition": "attachment; filename=results.csv"})
    if fmt == "xlsx":
        return Response(to_xlsx(rows),
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": "attachment; filename=results.xlsx"})
    return Response(to_json(rows), media_type="application/json")


@app.get("/api/export/submission")
def export_submission(authorization: Optional[str] = Header(None)):
    require_auth(authorization)
    payload = submission_payload(store.all_emails())
    return Response(json.dumps(payload, indent=2).encode(), media_type="application/json",
                    headers={"Content-Disposition": "attachment; filename=submission.json"})


@app.get("/api/export/audit")
def export_audit(
    authorization: Optional[str] = Header(None),
    fmt: str = "json",
    limit: int = 200,
):
    require_auth(authorization)
    rows = store.audit(limit=limit)
    if fmt == "csv":
        return Response(audit_to_csv(rows), media_type="text/csv",
                        headers={"Content-Disposition": "attachment; filename=audit.csv"})
    if fmt == "xlsx":
        return Response(to_xlsx([
            {"id": r.get("id"), "email_id": r.get("email_id"), "actor": r.get("actor"),
             "change_type": r.get("change_type"), "category": r.get("category"),
             "created_at": r.get("created_at")}
            for r in rows
        ]), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=audit.xlsx"})
    if fmt == "pdf":
        return Response(audit_to_pdf(rows), media_type="text/plain",
                        headers={"Content-Disposition": "attachment; filename=audit.txt"})
    return rows


def _run_ingest(job_id: int, root, emails, source, provider):
    store.update_job(job_id, status="running")
    done = failed = 0
    try:
        guard_vertex_batch(provider, len(emails))
    except RuntimeError as exc:
        store.update_job(job_id, status="failed", error=str(exc))
        # still store raw emails without live classify
        from seed import build_record
        for email in emails:
            rec = build_record(email, {}, root, source=source)
            store.upsert_email(rec, actor="program")
        return
    from seed import build_record
    for email in emails:
        try:
            rec = build_record(email, {}, root, source=source)
            decision = classify(provider, email, rec["attachments"])
            rec.update(decision)
            rec["processed_live"] = True
            store.upsert_email(rec, actor="program")
            done += 1
        except Exception as exc:
            failed += 1
            rec = build_record(email, {}, root, source=source)
            store.upsert_email(rec, actor="program")
            store.update_job(job_id, error=str(exc))
        store.update_job(job_id, done=done, failed=failed)
    store.update_job(job_id, status="done" if not failed else "failed", done=done, failed=failed)


def _run_process(job_id: int, ids: list[str], provider: str):
    store.update_job(job_id, status="running")
    done = failed = 0
    for eid in ids:
        rec = store.get_email(eid)
        if not rec:
            failed += 1
            continue
        try:
            email = {k: rec.get(k) for k in ("email_id", "from", "subject", "body", "attachments")}
            email["attachments"] = [
                a.get("rel") or f"attachments/{a.get('filename')}"
                for a in rec.get("attachments") or []
            ]
            decision = classify(provider, rec, rec.get("attachments") or [])
            rec.update(decision)
            rec["processed_live"] = True
            store.upsert_email(rec, actor="program",
                               change_type=f'reclassified with {provider}')
            done += 1
        except Exception as exc:
            failed += 1
            store.update_job(job_id, error=str(exc))
        store.update_job(job_id, done=done, failed=failed)
    store.update_job(job_id, status="done" if not failed else "failed", done=done, failed=failed)


@app.on_event("startup")
def startup():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="ui")
