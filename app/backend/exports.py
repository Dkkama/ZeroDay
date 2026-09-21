from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone

from config import CATEGORY_META, COMPARE_FIELDS
from store import public_email


def filter_emails(rows: list[dict], spec: dict) -> list[dict]:
    statuses = set(spec.get("statuses") or [])
    categories = set(spec.get("categories") or [])
    human_validated = spec.get("human_validated")
    out = []
    for rec in rows:
        if statuses and rec.get("status") not in statuses:
            continue
        if categories and rec.get("category") not in categories:
            continue
        if human_validated is True and not rec.get("human_validated"):
            continue
        if human_validated is False and rec.get("human_validated"):
            continue
        out.append(rec)
    return out


def preset_spec(name: str) -> dict:
    presets = {
        "all": {},
        "succeeded": {"statuses": ["OK"]},
        "mismatched": {"statuses": ["MISMATCH"]},
        "review": {"statuses": ["NEEDS_REVIEW"]},
        "succeeded_and_mismatched": {"statuses": ["OK", "MISMATCH"]},
        "validated": {"human_validated": True},
    }
    if name not in presets:
        raise ValueError(f"unknown preset {name}")
    return presets[name]


def results_rows(emails: list[dict]) -> list[dict]:
    rows = []
    for rec in emails:
        view = public_email(rec)
        row = {
            "email_id": rec.get("email_id"),
            "subject": rec.get("subject"),
            "from": rec.get("from"),
            "caught_at": rec.get("caught_at"),
            "category": rec.get("category"),
            "category_label": CATEGORY_META.get(rec.get("category"), {}).get("label"),
            "status": rec.get("status"),
            "review_reason": rec.get("review_reason"),
            "defect_fields": ",".join(rec.get("defect_fields") or []),
            "human_validated": rec.get("human_validated"),
            "last_actor": "human" if rec.get("human_validated") else "program",
        }
        for field in COMPARE_FIELDS:
            fv = next((f for f in view["field_view"] if f["name"] == field), {})
            row[f"{field}_si"] = fv.get("si") or ""
            row[f"{field}_bl"] = fv.get("bl") or ""
            row[f"{field}_resolved"] = fv.get("value") or ""
        rows.append(row)
    return rows


def to_csv(rows: list[dict]) -> bytes:
    if not rows:
        return b"email_id\n"
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


def to_json(rows: list[dict]) -> bytes:
    return json.dumps({"exported_at": datetime.now(timezone.utc).isoformat(),
                       "count": len(rows), "rows": rows}, indent=2).encode("utf-8")


def to_xlsx(rows: list[dict]) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "results"
    if not rows:
        ws.append(["email_id"])
    else:
        headers = list(rows[0].keys())
        ws.append(headers)
        for row in rows:
            ws.append([row.get(h) for h in headers])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def submission_payload(emails: list[dict]) -> dict:
    out = {}
    for rec in emails:
        out[rec["email_id"]] = {
            "category": rec.get("category") or "GENERAL",
            "status": rec.get("status") or "OK",
            "review_reason": rec.get("review_reason"),
            "has_defect": bool(rec.get("has_defect")),
            "defect_fields": list(rec.get("defect_fields") or []),
        }
    return out


def audit_to_csv(rows: list[dict]) -> bytes:
    flat = []
    for row in rows:
        flat.append({
            "id": row.get("id"),
            "email_id": row.get("email_id"),
            "actor": row.get("actor"),
            "change_type": row.get("change_type"),
            "category": row.get("category"),
            "created_at": row.get("created_at"),
            "details": json.dumps(row.get("details") or {}, ensure_ascii=False),
        })
    return to_csv(flat)


def audit_to_pdf(rows: list[dict]) -> bytes:
    lines = ["ZeroDay audit log", ""]
    for row in rows:
        lines.append(
            f"#{row.get('id')}  {row.get('created_at')}  {row.get('actor')}  "
            f"{row.get('email_id')}  {row.get('change_type')}"
        )
    return ("\n".join(lines) + "\n").encode("utf-8")
