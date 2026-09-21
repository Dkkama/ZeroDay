from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from config import (
    CURSOR_MODEL,
    GCP_PROJECT,
    PROMPT_PATH,
    ROOT,
    VERTEX_LOCATION,
    VERTEX_MAX_BATCH,
    VERTEX_MODEL,
)
from fields import empty_fields, extract_fields
from seed import attachment_kind, load_attachment


def system_prompt() -> str:
    return PROMPT_PATH.read_text()


def parse_model_json(text: str) -> dict:
    if not text:
        raise ValueError("empty model response")
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        obj = json.loads(cleaned)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", cleaned, re.S)
        if not m:
            raise
        obj = json.loads(m.group(0))
    if isinstance(obj, list):
        obj = obj[0]
    return obj


def apply_decision(email: dict, attachments: list[dict], raw: dict) -> dict:
    si_text = next((a.get("text") or "" for a in attachments if a.get("kind") == "si"), "")
    bl_text = next((a.get("text") or "" for a in attachments if a.get("kind") == "bl"), "")
    si_fields = raw.get("si_fields") if isinstance(raw.get("si_fields"), dict) else extract_fields(si_text)
    bl_fields = raw.get("bl_fields") if isinstance(raw.get("bl_fields"), dict) else extract_fields(bl_text)
    for key, default in empty_fields().items():
        si_fields.setdefault(key, default)
        bl_fields.setdefault(key, default)
    return {
        "category": raw.get("category") or "GENERAL",
        "status": raw.get("status") or "OK",
        "review_reason": raw.get("review_reason"),
        "has_defect": bool(raw.get("has_defect")),
        "defect_fields": list(raw.get("defect_fields") or []),
        "si_fields": si_fields,
        "bl_fields": bl_fields,
    }


def classify_cursor(email: dict, attachments: list[dict]) -> dict:
    sys.path.insert(0, str(ROOT / "sdoc_eval"))
    import run as runner  # noqa: E402

    key = os.environ.get("CURSOR_API_KEY") or os.environ.get("API_KEY") or ""
    if not key:
        raise RuntimeError("CURSOR_API_KEY is not set")
    api = {
        "key": key,
        "base": os.environ.get("CURSOR_API_BASE", "https://api.cursor.com"),
        "model": CURSOR_MODEL,
        "timeout": 180,
        "create_timeout": 180,
        "poll": 3.0,
        "reuse": True,
        "recycle_every": 0,
        "followup_limiter": None,
    }
    sys.path.insert(0, str(ROOT / "sdoc-hackathon-docker" / "server"))
    from loader import Inbox  # noqa: E402

    root = email.get("root") or str(ROOT / "sdoc-hackathon-docker" / "data_v2")
    rec, log = runner.process_one(
        email, Inbox(root), system_prompt(), api,
        retries=1, dry_run=False, vision=False, no_images=True,
    )
    if log.get("error") and not rec:
        raise RuntimeError(log.get("error"))
    return apply_decision(email, attachments, rec)


def _vertex_credentials():
    try:
        import google.auth
        creds, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        return creds
    except Exception:
        pass
    import subprocess
    from google.oauth2.credentials import Credentials

    out = subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        capture_output=True, text=True,
    )
    token = (out.stdout or "").strip()
    if out.returncode != 0 or not token:
        raise RuntimeError(
            "Vertex needs Google credentials. Run "
            "`gcloud auth application-default login` "
            f"(gcloud said: {(out.stderr or 'no token').strip()[:180]})"
        )
    return Credentials(token=token)


def classify_vertex(email: dict, attachments: list[dict]) -> dict:
    from google import genai
    from google.genai import types

    user = _user_prompt(email, attachments)
    creds = _vertex_credentials()
    client = genai.Client(
        vertexai=True,
        project=GCP_PROJECT,
        location=VERTEX_LOCATION,
        credentials=creds,
    )
    response = client.models.generate_content(
        model=VERTEX_MODEL,
        contents=f"{system_prompt()}\n\n{user}",
        config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_level="low"),
        ),
    )
    raw = parse_model_json(response.text or "")
    return apply_decision(email, attachments, raw)


def _runner_email(email: dict, attachments: list) -> dict:
    rels = []
    for att in attachments or email.get("attachments") or []:
        if isinstance(att, str):
            rels.append(att)
        elif att.get("rel"):
            rels.append(att["rel"])
        elif att.get("filename"):
            rels.append(f"attachments/{att['filename']}")
    return {
        "email_id": email.get("email_id"),
        "from": email.get("from"),
        "subject": email.get("subject"),
        "body": email.get("body"),
        "attachments": rels,
        "root": email.get("root"),
    }


def classify(provider: str, email: dict, attachments: list[dict]) -> dict:
    slim = _runner_email(email, attachments)
    if provider == "vertex":
        return classify_vertex(slim, attachments)
    if provider == "cursor":
        return classify_cursor(slim, attachments)
    raise ValueError(f"unknown provider {provider}")


def guard_vertex_batch(provider: str, n: int):
    if provider == "vertex" and n > VERTEX_MAX_BATCH:
        raise RuntimeError(
            f"Vertex demo quota is limited. Refusing to process {n} emails "
            f"(max {VERTEX_MAX_BATCH}). Switch Settings to Cursor (test) "
            "or process one email at a time."
        )


def _user_prompt(email: dict, attachments: list[dict]) -> str:
    sys.path.insert(0, str(ROOT / "sdoc_eval"))
    from extract import format_for_prompt  # noqa: E402

    blocks = [
        "You are answering a classification task for ONE email.",
        "Reply with a single JSON object and nothing else.",
        "",
        "## Email",
        f"email_id: {email.get('email_id')}",
        f"from: {email.get('from', '')}",
        f"subject: {email.get('subject', '')}",
        "",
        "body:",
        email.get("body") or "",
        "",
        "## Attachments",
    ]
    if not attachments:
        blocks.append("(none)")
    else:
        for rec in attachments:
            blocks.append(format_for_prompt(rec))
    blocks.append("")
    blocks.append(
        "Also include si_fields and bl_fields objects with the 7 compare keys "
        "when both documents are readable."
    )
    return "\n".join(blocks)


class _InboxShim:
    def __init__(self, email, attachments):
        self._email = email
        self._attachments = attachments

    def emails(self):
        return [self._email]

    def read_bytes(self, path):
        name = Path(path).name
        for att in self._attachments:
            if att.get("filename") == name and att.get("abs"):
                return Path(att["abs"]).read_bytes()
        return b""
