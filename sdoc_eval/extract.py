"""Pull readable text out of SI/BL attachments (txt / pdf / docx / xlsx).

PDFs with no text layer can be rendered to PNG pages for Cursor Cloud Agent
image inputs (Gemini / vision models). Max 5 images per agent prompt.
"""
from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path


def extract_attachment(filename: str, data: bytes, *,
                       render_pdf_images: bool = False,
                       max_pages: int = 2) -> dict:
    """Return {filename, ext, status, text, notes}.

    status:
      ok          — usable text extracted
      empty       — 0-byte or blank file
      unreadable  — no text layer, garbled, or parser failure
    """
    name = Path(filename).name
    ext = Path(filename).suffix.lower().lstrip(".")
    rec = {"filename": name, "ext": ext, "status": "ok", "text": "",
           "notes": "", "images": []}

    if not data:
        rec["status"] = "empty"
        rec["notes"] = "0-byte file"
        return rec

    try:
        if ext == "txt":
            text = data.decode("utf-8", errors="replace")
        elif ext == "pdf":
            text = _pdf_text(data)
        elif ext == "docx":
            text = _docx_text(data)
        elif ext == "xlsx":
            text = _xlsx_text(data)
        else:
            rec["status"] = "unreadable"
            rec["notes"] = f"unsupported extension .{ext}"
            return rec
    except Exception as exc:
        rec["status"] = "unreadable"
        rec["notes"] = f"{type(exc).__name__}: {exc}"
        text = ""

    text = (text or "").strip()
    if rec["status"] == "ok" and not text:
        rec["status"] = "unreadable"
        rec["notes"] = "no extractable text (image-only, empty, or garbled)"
    elif rec["status"] == "ok":
        rec["text"] = text
        rec["notes"] = f"{len(text)} chars"

    # Cloud Agents reject image payloads unless the selected model is
    # vision-enabled (gemini-3-flash is not). Only attach pages with --vision.
    want_images = ext == "pdf" and data and render_pdf_images
    if want_images:
        images, img_note = pdf_pages_as_images(data, max_pages=max_pages)
        rec["images"] = images
        if images:
            rec["notes"] = (rec["notes"] + "; " if rec["notes"] else "") + img_note
        elif img_note:
            rec["notes"] = (rec["notes"] + "; " if rec["notes"] else "") + img_note
    return rec


def format_for_prompt(rec: dict) -> str:
    header = f"### {rec['filename']}  [{rec['status']}]"
    if rec.get("notes"):
        header += f"  ({rec['notes']})"
    n_img = len(rec.get("images") or [])
    if n_img:
        header += f"  [{n_img} page image(s) attached]"
    if rec["status"] != "ok" and not rec.get("text") and not n_img:
        return header + "\n<unreadable — do not invent values>\n"
    if rec["status"] != "ok" and n_img and not rec.get("text"):
        return header + "\n<no text layer — read the attached page image(s) if possible>\n"
    if rec.get("text"):
        return header + "\n```\n" + rec["text"] + "\n```\n"
    return header + "\n"


def pdf_pages_as_images(data: bytes, max_pages: int = 2) -> tuple[list[dict], str]:
    """Render PDF pages to PNG dicts {data, mimeType} for the Cloud Agents API."""
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return [], "pypdfium2 not installed — cannot render PDF pages"

    try:
        pdf = pdfium.PdfDocument(data)
    except Exception as exc:
        return [], f"pdf render failed: {exc}"

    images = []
    n = min(len(pdf), max_pages)
    for i in range(n):
        page = pdf[i]
        bitmap = page.render(scale=1.5)
        pil = bitmap.to_pil()
        buf = BytesIO()
        pil.save(buf, format="PNG")
        images.append({
            "data": base64.b64encode(buf.getvalue()).decode("ascii"),
            "mimeType": "image/png",
        })
    return images, f"rendered {len(images)} page image(s)"


def _pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(data))
    parts = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n".join(parts)


def _docx_text(data: bytes) -> str:
    from docx import Document

    doc = Document(BytesIO(data))
    parts = [p.text for p in doc.paragraphs if p.text]
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            if any(cells):
                parts.append(" | ".join(cells))
    return "\n".join(parts)


def _xlsx_text(data: bytes) -> str:
    from openpyxl import load_workbook

    wb = load_workbook(BytesIO(data), data_only=True, read_only=True)
    parts = []
    for sheet in wb.worksheets:
        parts.append(f"[sheet: {sheet.title}]")
        for row in sheet.iter_rows(values_only=True):
            cells = ["" if c is None else str(c).strip() for c in row]
            if any(cells):
                parts.append(" | ".join(cells))
    wb.close()
    return "\n".join(parts)
