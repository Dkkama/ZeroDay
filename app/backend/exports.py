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


def audit_to_txt(rows: list[dict]) -> bytes:
    lines = ["ZeroDay audit log", ""]
    for row in rows:
        lines.append(
            f"#{row.get('id')}  {row.get('created_at')}  {row.get('actor')}  "
            f"{row.get('email_id')}  {row.get('change_type')}"
        )
    return ("\n".join(lines) + "\n").encode("utf-8")


def audit_to_pdf(rows: list[dict]) -> bytes:
    lines = ["ZeroDay audit log"]
    for row in rows:
        lines.append(
            f"#{row.get('id')}  {(row.get('created_at') or '')[:19]}  "
            f"{row.get('actor')}  {row.get('email_id')}  {row.get('change_type')}"
        )
    return _simple_pdf(lines)


def _pdf_escape(text: str) -> str:
    return (text or "").replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _simple_pdf(lines: list[str]) -> bytes:
    per_page = 48
    if not lines:
        lines = [""]
    chunks = [lines[i:i + per_page] for i in range(0, len(lines), per_page)]
    streams = []
    for chunk in chunks:
        cmds = ["BT", "/F1 10 Tf", "40 760 Td", "13 TL"]
        for i, line in enumerate(chunk):
            cmds.append(f"({_pdf_escape(line[:110])}) Tj")
            if i != len(chunk) - 1:
                cmds.append("T*")
        cmds.append("ET")
        streams.append("\n".join(cmds).encode("latin-1", errors="replace"))

    objects = ["<< /Type /Catalog /Pages 2 0 R >>", ""]
    content_ids, page_ids = [], []
    for stream in streams:
        objects.append(stream)
        content_ids.append(len(objects))
        objects.append(None)
        page_ids.append(len(objects))
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")
    font_id = len(objects)
    objects[1] = (
        f"<< /Type /Pages /Kids [{' '.join(f'{i} 0 R' for i in page_ids)}] "
        f"/Count {len(page_ids)} >>"
    )
    for cid, pid in zip(content_ids, page_ids):
        objects[pid - 1] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Contents {cid} 0 R /Resources << /Font << /F1 {font_id} 0 R >> >> >>"
        )

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(out))
        if isinstance(obj, bytes):
            out.extend(f"{i} 0 obj\n<< /Length {len(obj)} >>\nstream\n".encode())
            out.extend(obj)
            out.extend(b"\nendstream\nendobj\n")
        else:
            out.extend(f"{i} 0 obj\n{obj}\nendobj\n".encode())
    xref = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode())
    out.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(out)
