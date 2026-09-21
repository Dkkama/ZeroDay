#!/usr/bin/env python3
"""One Cursor Cloud Agent run per inbox email → sample_submission.json.

Uses your Cursor User API Key against https://api.cursor.com (Cloud Agents API).
That is how Cursor exposes the models on your subscription. There is no
chat/completions endpoint. A small pool of no-repo cloud agents is kept warm;
each email is a follow-up run on a reused VM, with a reset banner so prior
cases are ignored. Agents are recycled after --recycle-every turns.

    cp .env.example .env              # CURSOR_API_KEY=...
    pip install -r sdoc_eval/requirements.txt

    python sdoc_eval/run.py --whoami
    python sdoc_eval/run.py --list-models
    python sdoc_eval/run.py --dry-run --limit 3
    python sdoc_eval/run.py --pilot --model <id-from-list-models> --concurrency 12
    python sdoc_eval/run.py --model gemini-3.1-pro --concurrency 12
    python sdoc_eval/run.py --resume sdoc_eval/outputs/submission.json

Cloud agents are slower than a chat API (VM spin-up). Use --pilot first.
Do not run the full 520-email sweep from the IDE.
"""
from __future__ import annotations

import argparse
import json
import os
import queue
import re
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA_DIR = ROOT / "sdoc-hackathon-docker" / "data_v2"
SERVER_DIR = ROOT / "sdoc-hackathon-docker" / "server"
DEFAULT_PROMPT = HERE / "prompts" / "v1.md"
DEFAULT_OUT = HERE / "outputs"
DEFAULT_BASE = "https://api.cursor.com"
MAX_IMAGES = 5

sys.path.insert(0, str(SERVER_DIR))
from loader import Inbox  # noqa: E402
import scoring  # noqa: E402

from extract import extract_attachment, format_for_prompt  # noqa: E402

CATEGORIES = ["BL_COMPARISON", "SI_REQUEST", "INVOICE_QUERY", "GENERAL", "SPAM"]
STATUSES = ["OK", "MISMATCH", "NEEDS_REVIEW"]
REVIEW_REASONS = ["wrong_doc_type", "missing_attachment", "unreadable", "missing_value"]
COMPARE_FIELDS = [
    "shipper", "consignee", "notify_party",
    "port_of_loading", "port_of_discharge",
    "container_count", "gross_weight_kg",
]
DEFAULT_RECORD = {
    "category": "GENERAL",
    "status": "OK",
    "review_reason": None,
    "defect_fields": [],
    "has_defect": False,
}
TERMINAL = {"FINISHED", "ERROR", "CANCELLED", "EXPIRED"}


def env_key() -> str:
    for name in ("CURSOR_API_KEY", "API_KEY"):
        val = (os.environ.get(name) or "").strip()
        if val:
            return val
    return ""


def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", default=str(DATA_DIR), help="folder with inbox/ + attachments/")
    p.add_argument("--prompt", default=str(DEFAULT_PROMPT), help="system prompt markdown")
    p.add_argument("--model", default=os.environ.get("CURSOR_MODEL", ""),
                   help="model.id from --list-models (omit to use your Cursor default)")
    p.add_argument("--api-base", default=os.environ.get("CURSOR_API_BASE", DEFAULT_BASE),
                   help="Cursor API host, default https://api.cursor.com")
    p.add_argument("--out", default=str(DEFAULT_OUT), help="output directory")
    p.add_argument("--limit", type=int, default=0, help="process at most N selected emails")
    p.add_argument("--offset", type=int, default=0)
    p.add_argument("--ids", default="", help="comma-separated email_ids")
    p.add_argument("--pilot", action="store_true",
                   help="stratified ~40-email mix (all formats + edge cases 501-520)")
    p.add_argument("--resume", default="", help="existing submission.json to continue")
    p.add_argument("--force", action="store_true", help="re-call the API even if email is in processed.json")
    p.add_argument("--retries", type=int, default=2)
    p.add_argument("--timeout", type=int, default=300, help="seconds to wait for one agent run")
    p.add_argument("--create-timeout", type=int, default=180,
                   help="seconds to wait for POST /v1/agents to return")
    p.add_argument("--poll", type=float, default=3.0, help="seconds between run-status polls")
    p.add_argument("--concurrency", type=int, default=3,
                   help="warm VMs. 300 follow-ups/hour ⇒ ~5/min; 2–3 in-flight is enough.")
    p.add_argument("--followup-rpm", type=int, default=5,
                   help="max POST /v1/agents/{id}/runs per minute (Cursor also has 30/min; "
                        "300/hour is the binding cap, so default is 5)")
    p.add_argument("--followup-rph", type=int, default=280,
                   help="max follow-up POSTs per rolling hour (Cursor limit is 300)")
    p.add_argument("--batch", type=int, default=8,
                   help="emails per follow-up POST (300/hour cap; 8 ⇒ ~65 POSTs for 520)")
    p.add_argument("--no-reuse", action="store_true",
                   help="create and archive a VM for every email (slow)")
    p.add_argument("--recycle-every", type=int, default=0,
                   help="new VM after this many emails on a worker (0 = keep until the VM dies)")
    p.add_argument("--vision", action="store_true",
                   help="also render text-PDFs to page images (image-only PDFs always try)")
    p.add_argument("--no-images", action="store_true", help="never attach page images")
    p.add_argument("--dry-run", action="store_true", help="build prompts, do not call the API")
    p.add_argument("--score-only", default="", help="score an existing submission and exit")
    p.add_argument("--no-score", action="store_true")
    p.add_argument("--list-models", action="store_true")
    p.add_argument("--whoami", action="store_true")
    return p.parse_args()


def empty_submission(email_ids):
    return {eid: dict(DEFAULT_RECORD) for eid in email_ids}


def load_json(path: Path, default=None):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def save_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def _strip_fences(text: str) -> str:
    cleaned = (text or "").strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _match_bracket(text: str, start: int) -> int:
    open_ch = text[start]
    close_ch = "}" if open_ch == "{" else "]"
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return i
    return -1


def _iter_json_values(text: str):
    i = 0
    while i < len(text):
        if text[i] in "[{":
            end = _match_bracket(text, i)
            if end > i:
                chunk = text[i:end + 1]
                try:
                    yield json.loads(chunk)
                    i = end + 1
                    continue
                except json.JSONDecodeError:
                    pass
        i += 1


def extract_json_object(text: str) -> dict:
    if not text:
        raise ValueError("empty model response")
    cleaned = _strip_fences(text)
    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict):
            return obj
        if isinstance(obj, list) and obj and isinstance(obj[0], dict):
            return obj[0]
    except json.JSONDecodeError:
        pass
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in model response")
    obj = json.loads(cleaned[start:end + 1])
    if not isinstance(obj, dict):
        raise ValueError("JSON is not an object")
    return obj


def extract_json_records(text: str, expected_ids: list[str]) -> dict:
    """Map email_id → raw model object. Missing ids are omitted."""
    if not text:
        raise ValueError("empty model response")
    expected = set(expected_ids)
    records = {}

    def ingest(obj):
        if isinstance(obj, list):
            for item in obj:
                ingest(item)
            return
        if not isinstance(obj, dict):
            return
        nested = [k for k in obj if k in expected and isinstance(obj[k], dict)]
        if nested:
            for k in nested:
                records[k] = obj[k]
            return
        eid = obj.get("email_id")
        if eid in expected:
            records[eid] = obj
        elif len(expected_ids) == 1 and "category" in obj:
            records[expected_ids[0]] = obj

    cleaned = _strip_fences(text)
    try:
        ingest(json.loads(cleaned))
    except json.JSONDecodeError:
        for value in _iter_json_values(cleaned):
            ingest(value)
    if not records:
        raise ValueError("no JSON records for expected email_ids")
    return records


def normalize_record(raw: dict) -> dict:
    cat = str(raw.get("category", "GENERAL")).strip().upper()
    if cat not in CATEGORIES:
        cat = "GENERAL"
    status = str(raw.get("status", "OK")).strip().upper()
    if status not in STATUSES:
        status = "OK"
    reason = raw.get("review_reason")
    if isinstance(reason, str):
        reason = reason.strip().lower() or None
    if reason not in REVIEW_REASONS:
        reason = None
    fields = raw.get("defect_fields") or []
    if not isinstance(fields, list):
        fields = []
    fields = [f for f in fields if f in COMPARE_FIELDS]

    if cat != "BL_COMPARISON":
        return dict(DEFAULT_RECORD, category=cat)

    if status == "MISMATCH":
        if not fields:
            return {
                "category": cat, "status": "OK", "review_reason": None,
                "defect_fields": [], "has_defect": False,
            }
        return {
            "category": cat, "status": "MISMATCH", "review_reason": None,
            "defect_fields": fields, "has_defect": True,
        }
    if status == "NEEDS_REVIEW":
        return {
            "category": cat, "status": "NEEDS_REVIEW",
            "review_reason": reason or "unreadable",
            "defect_fields": [], "has_defect": False,
        }
    return {
        "category": cat, "status": "OK", "review_reason": None,
        "defect_fields": [], "has_defect": False,
    }


def rough_bucket(email: dict) -> str:
    atts = email.get("attachments") or []
    if atts:
        exts = "+".join(sorted(Path(a).suffix.lower() for a in atts))
        return f"att{exts}"
    subj = (email.get("subject") or "").lower()
    body = (email.get("body") or "").lower()
    blob = subj + " " + body
    if any(k in blob for k in ("won", "gift card", "parcel is on hold", "bitcoin",
                               "hot singles", "mailbox", "verify account")):
        return "spam"
    if any(k in blob for k in ("invoice", "freight", "billing", "d & d", "local charges")):
        return "invoice"
    if re.search(r"\bsi\b", blob) and "confirm" not in blob and "draft bl" not in blob:
        return "si"
    if any(k in blob for k in ("confirm docs", "draft bl", "request bl", "compare")):
        return "bl"
    return "general"


def pick_pilot(emails: list[dict]) -> list[dict]:
    by_id = {e["email_id"]: e for e in emails}
    chosen = []
    seen = set()

    def take(e):
        if e["email_id"] not in seen:
            seen.add(e["email_id"])
            chosen.append(e)

    for i in range(501, 521):
        e = by_id.get(f"email_{i:03d}")
        if e:
            take(e)

    buckets = {}
    for e in emails:
        buckets.setdefault(rough_bucket(e), []).append(e)
    for rows in buckets.values():
        for e in rows[:3]:
            take(e)

    chosen.sort(key=lambda e: e["email_id"])
    return chosen


def select_emails(emails, args) -> list[dict]:
    if args.ids:
        want = {x.strip() for x in args.ids.split(",") if x.strip()}
        selected = [e for e in emails if e["email_id"] in want]
    elif args.pilot:
        selected = pick_pilot(emails)
    else:
        selected = list(emails)
    selected = selected[args.offset:]
    if args.limit:
        selected = selected[:args.limit]
    return selected


def load_attachments(inbox: Inbox, email: dict, *, vision: bool, no_images: bool) -> list[dict]:
    recs = []
    for rel in email.get("attachments") or []:
        data = inbox.read_bytes(rel)
        recs.append(extract_attachment(
            rel, data,
            render_pdf_images=(vision and not no_images),
            max_pages=2,
        ))
        if no_images:
            recs[-1]["images"] = []
    return recs


def collect_images(atts: list[dict]) -> list[dict]:
    images = []
    for rec in atts:
        for img in rec.get("images") or []:
            images.append(img)
            if len(images) >= MAX_IMAGES:
                return images
    return images


def build_user_message(email: dict, atts: list[dict]) -> str:
    return build_batch_user_message([(email, atts)])


def build_batch_user_message(cases: list[tuple[dict, list]]) -> str:
    n = len(cases)
    ids = [email["email_id"] for email, _ in cases]
    if n == 1:
        email, atts = cases[0]
        blocks = [
            "You are answering a classification task for ONE email.",
            "Do not use tools, do not edit files, do not browse the workspace.",
            "Reply with a single JSON object and nothing else.",
            "",
            "## Email",
            f"email_id: {email['email_id']}",
            f"from: {email.get('from', '')}",
            f"subject: {email.get('subject', '')}",
            "", "body:", email.get("body") or "",
            "", "## Attachments",
        ]
        if not atts:
            blocks.append("(none)")
        else:
            for rec in atts:
                blocks.append(format_for_prompt(rec))
        blocks.append("")
        blocks.append("Return only the JSON object for this email_id.")
        return "\n".join(blocks)

    blocks = [
        f"Classify {n} independent emails. Each case is a separate decision.",
        "Do not use tools, do not edit files, do not browse the workspace.",
        "Do not copy category, status, or field values from one case to another.",
        f"Reply with a JSON array of {n} objects and nothing else.",
        f"Required email_ids in this order: {', '.join(ids)}",
        "",
    ]
    for i, (email, atts) in enumerate(cases, 1):
        blocks.append(f"======== CASE {i} / {email['email_id']} ========")
        blocks.append(f"email_id: {email['email_id']}")
        blocks.append(f"from: {email.get('from', '')}")
        blocks.append(f"subject: {email.get('subject', '')}")
        blocks.append("")
        blocks.append("body:")
        blocks.append(email.get("body") or "")
        blocks.append("")
        blocks.append("## Attachments")
        if not atts:
            blocks.append("(none)")
        else:
            for rec in atts:
                blocks.append(format_for_prompt(rec))
        blocks.append("")
    blocks.append(
        f"Return only a JSON array of {n} objects, each including email_id, "
        "in the same order as the cases."
    )
    return "\n".join(blocks)


def strip_private(submission: dict) -> dict:
    clean = {}
    for eid, rec in submission.items():
        clean[eid] = {k: v for k, v in rec.items() if not k.startswith("_")}
    return clean


class ApiError(Exception):
    def __init__(self, status, payload, retry_after):
        self.status = status
        self.payload = payload
        self.retry_after = retry_after
        msg = payload.get("message") or payload.get("error") if isinstance(payload, dict) else payload
        if isinstance(msg, dict):
            msg = msg.get("message") or json.dumps(msg)
        super().__init__(f"HTTP {status}: {msg}")

    @property
    def retryable(self) -> bool:
        return self.status in (0, 408, 409, 429, 500, 502, 503, 504)

    def retry_wait(self, attempt: int) -> float:
        if self.retry_after:
            try:
                raw = float(self.retry_after)
                # Unix timestamp → remaining seconds
                if raw > 1e9:
                    raw = raw - time.time()
                # Cursor often sends Retry-After in milliseconds
                elif raw > 180:
                    raw = raw / 1000.0
                return min(65.0, max(1.0, raw))
            except ValueError:
                pass
        return min(30.0, 2 ** attempt)


def cursor_request(method: str, url: str, api_key: str, body=None, timeout=60):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, json.loads(raw) if raw else {}, dict(resp.headers)
    except urllib.error.HTTPError as err:
        raw = err.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"error": raw[:800]}
        retry_after = err.headers.get("Retry-After") if err.headers else None
        raise ApiError(err.code, payload, retry_after) from err
    except socket.timeout as err:
        raise ApiError(408, {"error": f"socket timeout after {timeout}s: {err}"},
                       str(min(10, timeout))) from err
    except TimeoutError as err:
        raise ApiError(408, {"error": f"timeout after {timeout}s: {err}"},
                       str(min(10, timeout))) from err
    except urllib.error.URLError as err:
        reason = err.reason
        if isinstance(reason, socket.timeout) or "timed out" in str(reason).lower():
            raise ApiError(408, {"error": f"url timeout after {timeout}s: {reason}"},
                           str(min(10, timeout))) from err
        raise ApiError(0, {"error": str(reason)}, None) from err


def api_url(base: str, path: str) -> str:
    return base.rstrip("/") + path


def wait_for_run(api_key: str, base: str, agent_id: str, run_id: str,
                 timeout: int, poll: float):
    deadline = time.time() + timeout
    last = {}
    while time.time() < deadline:
        _, last, _ = cursor_request(
            "GET",
            api_url(base, f"/v1/agents/{agent_id}/runs/{run_id}"),
            api_key,
            timeout=60,
        )
        if last.get("status") in TERMINAL:
            return last
        time.sleep(poll)
    raise ApiError(0, {"error": f"run {run_id} timed out after {timeout}s "
                                f"(last status={last.get('status')})"}, None)


class RateLimiter:
    """Thread-safe sliding windows, e.g. 5/min and 280/hour together."""

    def __init__(self, windows):
        # windows: list of (max_calls, period_s)
        self.windows = [(max(1, int(n)), float(p)) for n, p in windows]
        self._times = []
        self._lock = threading.Lock()

    def wait(self):
        while True:
            sleep_for = 0.0
            label = ""
            with self._lock:
                now = time.time()
                longest = max(p for _, p in self.windows)
                self._times = [t for t in self._times if now - t < longest]
                for limit, period in self.windows:
                    recent = [t for t in self._times if now - t < period]
                    if len(recent) >= limit:
                        wait = period - (now - recent[0]) + 0.05
                        if wait > sleep_for:
                            sleep_for = wait
                            if period >= 3600:
                                label = f"hourly {limit}/{period:.0f}s"
                            elif period >= 60:
                                label = f"per-minute {limit}/{period:.0f}s"
                            else:
                                label = f"{limit}/{period:.0f}s"
                if sleep_for <= 0:
                    self._times.append(now)
                    return
            print(f"    follow-up rate limit ({label}), sleep {sleep_for:.1f}s",
                  flush=True)
            time.sleep(sleep_for)


def archive_agent(api_key: str, base: str, agent_id: str):
    try:
        cursor_request("POST", api_url(base, f"/v1/agents/{agent_id}/archive"),
                       api_key, timeout=30)
    except ApiError:
        pass


RESET_BANNER = (
    "NEW INDEPENDENT BATCH.\n"
    "Ignore every previous email, attachment, and JSON in this conversation.\n"
    "Do not copy field values from earlier turns or across cases below.\n"
    "Use only the documents in this message.\n"
)

BATCH_ADDENDUM = """
## Batch mode
You will receive several independent emails in one user message.
Classify EACH separately. Never reuse shipper, ports, status, or defect_fields
from another case in the same batch or from an earlier turn.
Reply with a JSON array only — one object per email, each including email_id:
[
  {"email_id": "email_001", "category": "...", "status": "...", "review_reason": null, "has_defect": false, "defect_fields": []},
  ...
]
No markdown fences, no commentary.
""".strip()


class AgentSession:
    """One warm no-repo Cloud Agent VM. Follow-up runs reuse it."""

    def __init__(self, api, worker_id=0):
        self.api = api
        self.worker_id = worker_id
        self.agent_id = None
        self.turns = 0

    def close(self):
        if self.agent_id:
            print(f"    worker-{self.worker_id} archive {self.agent_id}", flush=True)
            archive_agent(self.api["key"], self.api["base"], self.agent_id)
            self.agent_id = None
            self.turns = 0

    def run(self, system: str, user: str, images: list[dict], email_id: str):
        reuse = not self.api.get("no_reuse")
        recycle_every = int(self.api.get("recycle_every") or 0)
        if reuse and self.agent_id and recycle_every and self.turns >= recycle_every:
            print(f"    {email_id} recycle worker-{self.worker_id} after {self.turns} turns",
                  flush=True)
            self.close()

        follow_up = bool(reuse and self.agent_id)
        # Re-sending the full system prompt on every follow-up copies it into
        # history N times and blows token cost. The first create already has it.
        if follow_up:
            text = RESET_BANNER + "\n" + user
        else:
            text = system.strip() + "\n\n" + user
        prompt = {"text": text}
        if images:
            prompt["images"] = images[:MAX_IMAGES]

        if follow_up:
            run_id = self._follow_up(prompt, email_id)
            agent_id = self.agent_id
        else:
            agent_id, run_id = self._create(prompt, email_id)
            self.agent_id = agent_id

        print(f"    {email_id} agent={agent_id}  run={run_id}  "
              f"{'reuse' if follow_up else 'new'}  waiting …", flush=True)
        try:
            finished = wait_for_run(self.api["key"], self.api["base"], agent_id, run_id,
                                    timeout=self.api["timeout"], poll=self.api["poll"])
        except Exception:
            # dead VM — next email will create a new one
            self.close()
            raise

        if not reuse:
            self.close()
        else:
            self.turns += 1

        status = finished.get("status")
        raw = finished.get("result") or ""
        meta = {"agent_id": agent_id, "run_id": run_id, "run_status": status,
                "duration_ms": finished.get("durationMs"), "reused": follow_up,
                "turns_on_vm": self.turns}
        if status != "FINISHED":
            if reuse:
                self.close()
            return {"ok": False, "error": f"run status={status}",
                    "retryable": status in ("ERROR", "EXPIRED"),
                    "retry_after": 3, "raw": raw, "status": status, "meta": meta}
        if not raw:
            return {"ok": False, "error": "empty run result",
                    "retryable": True, "retry_after": 2, "raw": "",
                    "status": status, "meta": meta}
        return {"ok": True, "error": None, "retryable": False, "retry_after": None,
                "raw": raw, "status": status, "meta": meta}

    def _create(self, prompt, email_id):
        body = {
            "prompt": prompt,
            "name": f"sdoc-w{self.worker_id}"[:100],
        }
        if self.api.get("model"):
            body["model"] = {"id": self.api["model"]}
        create_timeout = int(self.api.get("create_timeout") or 180)
        print(f"    {email_id} worker-{self.worker_id} creating VM "
              f"({self.api.get('model') or 'default'}) …", flush=True)
        _, created, _ = cursor_request(
            "POST", api_url(self.api["base"], "/v1/agents"),
            self.api["key"], body, timeout=create_timeout,
        )
        agent = created.get("agent") or {}
        run = created.get("run") or {}
        agent_id = agent.get("id")
        run_id = run.get("id") or agent.get("latestRunId")
        if not agent_id or not run_id:
            raise ApiError(0, {"error": f"create returned no ids: {created}"}, None)
        return agent_id, run_id

    def _follow_up(self, prompt, email_id):
        url = api_url(self.api["base"], f"/v1/agents/{self.agent_id}/runs")
        last_err = None
        limiter = self.api.get("followup_limiter")
        for attempt in range(8):
            try:
                if limiter:
                    limiter.wait()
                _, data, _ = cursor_request(
                    "POST", url, self.api["key"], {"prompt": prompt}, timeout=120,
                )
                run = data.get("run") or data
                run_id = run.get("id")
                if not run_id:
                    raise ApiError(0, {"error": f"follow-up returned no run id: {data}"}, None)
                return run_id
            except ApiError as err:
                last_err = err
                if err.status == 409:
                    time.sleep(self.api.get("poll") or 3.0)
                    continue
                if err.status == 429:
                    wait = err.retry_wait(attempt)
                    print(f"    {email_id} follow-up 429, sleep {wait:.1f}s", flush=True)
                    time.sleep(wait)
                    continue
                if err.status in (404, 410):
                    print(f"    {email_id} follow-up {err.status}, new VM", flush=True)
                    self.close()
                    agent_id, run_id = self._create(prompt, email_id)
                    self.agent_id = agent_id
                    return run_id
                raise
        raise last_err or ApiError(409, {"error": "agent_busy retries exhausted"}, None)


def _case_log(email, atts, images, system, user):
    return {
        "email_id": email["email_id"],
        "attachments": [{k: rec[k] for k in ("filename", "ext", "status", "notes")}
                        for rec in atts],
        "n_images": len(images),
        "prompt_chars": len(system) + len(user),
        "batch_ids": None,
    }


def prepare_batch(emails, inbox, vision, no_images, batch_size):
    """Load attachments. Drop later emails if the 5-image cap would be exceeded."""
    cases = []
    leftover = []
    n_img = 0
    for email in emails:
        if leftover:
            leftover.append(email)
            continue
        atts = load_attachments(inbox, email, vision=vision, no_images=no_images)
        images = collect_images(atts)
        if cases and (len(cases) >= batch_size or n_img + len(images) > MAX_IMAGES):
            leftover.append(email)
            continue
        cases.append((email, atts, images))
        n_img += len(images)
    return cases, leftover


def process_batch(emails, inbox, system, api, retries, dry_run, vision, no_images,
                  session=None, batch_size=1):
    cases, leftover = prepare_batch(emails, inbox, vision, no_images, batch_size)
    pairs = [(email, atts) for email, atts, _ in cases]
    images = []
    for _, _, imgs in cases:
        for img in imgs:
            if len(images) >= MAX_IMAGES:
                break
            images.append(img)
        if len(images) >= MAX_IMAGES:
            break
    user = build_batch_user_message(pairs)
    ids = [email["email_id"] for email, _, _ in cases]
    label = ",".join(ids)
    logs = {email["email_id"]: _case_log(email, atts, imgs, system, user)
            for email, atts, imgs in cases}
    for log in logs.values():
        log["batch_ids"] = ids

    def defaults(err, status="error"):
        out = []
        for email, _, _ in cases:
            log = logs[email["email_id"]]
            log["error"] = err
            log["status"] = status
            out.append((email, dict(DEFAULT_RECORD), log))
        return out, leftover

    if dry_run:
        out = []
        for email, _, _ in cases:
            log = logs[email["email_id"]]
            log["dry_run"] = True
            log["user_preview"] = user[:2000]
            out.append((email, dict(DEFAULT_RECORD), log))
        return out, leftover

    last_err = "unknown"
    raw = ""
    api = dict(api, email_id=label)
    sess = session or AgentSession(api, worker_id=0)
    own_session = session is None
    for attempt in range(retries + 1):
        try:
            resp = sess.run(system, user, images, label)
        except ApiError as err:
            last_err = str(err)
            print(f"    {last_err}", flush=True)
            if err.retryable and attempt < retries:
                wait = err.retry_wait(attempt)
                print(f"    retry {attempt + 1}/{retries} in {wait:.0f}s", flush=True)
                time.sleep(wait)
                continue
            if own_session:
                sess.close()
            return defaults(last_err, f"http_{err.status}")
        except Exception as err:
            last_err = f"{type(err).__name__}: {err}"
            print(f"    {last_err}", flush=True)
            if attempt < retries:
                time.sleep(2 ** attempt)
                continue
            if own_session:
                sess.close()
            return defaults(last_err, "exception")

        raw = resp["raw"]
        if not resp["ok"]:
            last_err = resp["error"]
            if resp["retryable"] and attempt < retries:
                time.sleep(resp.get("retry_after") or 2 ** attempt)
                continue
            if own_session:
                sess.close()
            return defaults(last_err, resp.get("status") or "error")
        try:
            parsed = extract_json_records(raw, ids)
        except (ValueError, json.JSONDecodeError) as exc:
            last_err = f"parse: {exc}"
            if attempt < retries:
                time.sleep(1)
                continue
            if own_session:
                sess.close()
            return defaults(last_err, "parse")

        out = []
        for email, _, _ in cases:
            eid = email["email_id"]
            log = logs[eid]
            log["raw"] = raw
            log["status"] = resp["status"]
            log["agent"] = resp.get("meta")
            if eid in parsed:
                rec = normalize_record(parsed[eid])
                log["parsed"] = rec
                out.append((email, rec, log))
            else:
                log["error"] = "parse: email_id missing from batch response"
                out.append((email, dict(DEFAULT_RECORD), log))
        return out, leftover

    if own_session:
        sess.close()
    return defaults(last_err)


def process_one(email, inbox, system, api, retries, dry_run, vision, no_images,
                session=None):
    rows, _ = process_batch(
        [email], inbox, system, api, retries, dry_run, vision, no_images,
        session=session, batch_size=1,
    )
    _, rec, log = rows[0]
    return rec, log


def score_submission(submission: dict, truth: dict, processed_ids=None):
    if processed_ids:
        truth = {k: v for k, v in truth.items() if k in processed_ids}
        submission = {k: submission[k] for k in truth}
    return scoring.score_all(truth, submission)


def print_score(r, label):
    s1, s3, rel, e2e = r["stage1"], r["stage3"], r["reliability"], r["end_to_end"]
    print(f"\n=== score ({label}, n={r['n_emails']}) ===")
    print(f"  stage1 macro-F1   {s1['macro_f1']:.3f}   acc {s1['accuracy']:.3f}")
    print(f"  stage3 defect-F1  {s3['defect_f1']:.3f}   field-F1 {s3['field_f1']:.3f}")
    print(f"  reliability F1    {rel['escalation_f1']:.3f}   "
          f"gold_review={rel['gold_review']} pred_review={rel['pred_review']}")
    print(f"  end-to-end        {e2e['success']}/{e2e['total']}  {e2e['rate']:.3f}")
    print(f"  FINAL             {r['final_score']:.4f}")


def cmd_whoami(api_key: str, base: str):
    _, data, _ = cursor_request("GET", api_url(base, "/v1/me"), api_key, timeout=30)
    print(json.dumps(data, indent=2))


def cmd_list_models(api_key: str, base: str):
    _, data, _ = cursor_request("GET", api_url(base, "/v1/models"), api_key, timeout=30)
    items = data.get("items") or data.get("models") or []
    if not items:
        print(json.dumps(data, indent=2)[:3000])
        return
    print(f"{'id':<40} displayName")
    print("-" * 72)
    for row in items:
        mid = row.get("id", "")
        name = row.get("displayName") or ""
        print(f"{mid:<40} {name}")
        aliases = row.get("aliases") or []
        if aliases:
            print(f"  aliases: {', '.join(aliases)}")


def main():
    load_dotenv(ROOT / ".env")
    args = parse_args()
    api_key = env_key()
    api_base = args.api_base.rstrip("/")

    if args.whoami or args.list_models:
        if not api_key:
            sys.exit("CURSOR_API_KEY missing — copy .env.example to .env")
        if args.whoami:
            cmd_whoami(api_key, api_base)
        if args.list_models:
            cmd_list_models(api_key, api_base)
        return

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    sub_path = Path(args.resume) if args.resume else out_dir / "submission.json"
    logs_dir = out_dir / "logs"
    gt_path = Path(args.data) / "ground_truth.json"
    truth = load_json(gt_path, {})

    if args.score_only:
        sub = json.loads(Path(args.score_only).read_text(encoding="utf-8"))
        if not truth:
            sys.exit(f"no ground truth at {gt_path}")
        r = score_submission(strip_private(sub), truth)
        print_score(r, Path(args.score_only).name)
        save_json(out_dir / "score.json", r)
        return

    inbox = Inbox(args.data)
    emails = inbox.emails()
    all_ids = [e["email_id"] for e in emails]
    selected = select_emails(emails, args)
    if not selected:
        sys.exit("no emails selected")

    submission = load_json(sub_path, None) or empty_submission(all_ids)
    for eid in all_ids:
        submission.setdefault(eid, dict(DEFAULT_RECORD))
    done_path = sub_path.parent / "processed.json"
    done_ids = set(load_json(done_path, []) or [])

    system = Path(args.prompt).read_text(encoding="utf-8")
    batch_size = max(1, args.batch)
    if batch_size > 1:
        system = system.rstrip() + "\n\n" + BATCH_ADDENDUM
    if not args.dry_run and not api_key:
        sys.exit("CURSOR_API_KEY missing — copy .env.example to .env")

    api = {
        "key": api_key,
        "base": api_base,
        "model": (args.model or "").strip(),
        "timeout": args.timeout,
        "create_timeout": args.create_timeout,
        "poll": args.poll,
        "no_reuse": args.no_reuse,
        "recycle_every": args.recycle_every,
        "followup_limiter": RateLimiter([
            (args.followup_rpm, 60.0),
            (args.followup_rph, 3600.0),
        ]),
    }

    todo = []
    processed = []
    for email in selected:
        eid = email["email_id"]
        if eid in done_ids and not args.force:
            processed.append(eid)
            continue
        todo.append(email)
    workers = 1 if args.dry_run else max(1, args.concurrency)
    print(f"base={api_base}  model={api['model'] or '(account default)'}  "
          f"selected={len(selected)}  todo={len(todo)}  concurrency={workers}  "
          f"reuse={not args.no_reuse}  recycle_every={args.recycle_every}  "
          f"followup_rpm={args.followup_rpm}  followup_rph={args.followup_rph}  "
          f"batch={batch_size}  "
          f"inbox={len(emails)}  out={sub_path}")
    if processed and not args.force:
        print(f"skipping {len(processed)} already processed (use --force to redo)")

    lock = threading.Lock()
    t0 = time.time()

    def commit(eid, rec, log):
        with lock:
            if not args.dry_run:
                submission[eid] = rec
                save_json(sub_path, strip_private(submission))
                done_ids.add(eid)
                save_json(done_path, sorted(done_ids))
            save_json(logs_dir / f"{eid}.json", log)
            processed.append(eid)
            n = len(processed)
        extra = rec["category"]
        if rec["status"] != "OK":
            extra += f" {rec['status']}"
        if rec["defect_fields"]:
            extra += f" {rec['defect_fields']}"
        if rec.get("review_reason"):
            extra += f" {rec['review_reason']}"
        if log.get("error"):
            extra += f" ERR {log['error']}"
        print(f"[{n}/{len(selected)}] {eid}  {extra}", flush=True)

    def take_emails(q, n):
        grabbed = []
        for _ in range(n):
            try:
                grabbed.append(q.get_nowait())
            except queue.Empty:
                break
        return grabbed

    if args.dry_run:
        pending = list(todo)
        while pending:
            chunk, rest = pending[:batch_size], pending[batch_size:]
            rows, leftover = process_batch(
                chunk, inbox, system, api, args.retries, True,
                vision=args.vision, no_images=args.no_images,
                batch_size=batch_size,
            )
            for email, rec, log in rows:
                commit(email["email_id"], rec, log)
            pending = leftover + rest
    else:
        work_q = queue.Queue()
        for email in todo:
            work_q.put(email)

        def worker_loop(worker_id):
            sess = AgentSession(api, worker_id=worker_id)
            pending = []
            try:
                while True:
                    if not pending:
                        pending = take_emails(work_q, batch_size)
                    if not pending:
                        return
                    try:
                        rows, leftover = process_batch(
                            pending, inbox, system, api, args.retries, False,
                            vision=args.vision, no_images=args.no_images,
                            session=sess, batch_size=batch_size,
                        )
                        for email, rec, log in rows:
                            commit(email["email_id"], rec, log)
                        pending = leftover
                    except Exception as err:
                        for email in pending:
                            commit(email["email_id"], dict(DEFAULT_RECORD), {
                                "email_id": email["email_id"],
                                "error": f"{type(err).__name__}: {err}",
                            })
                        pending = []
            finally:
                sess.close()

        threads = [
            threading.Thread(target=worker_loop, args=(i,), name=f"sdoc-w{i}")
            for i in range(workers)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    public = strip_private(submission)
    save_json(sub_path, public)
    meta = {
        "api_base": api_base,
        "model": api["model"] or None,
        "prompt": str(Path(args.prompt).resolve()),
        "processed": processed,
        "dry_run": args.dry_run,
        "elapsed_s": round(time.time() - t0, 1),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    save_json(out_dir / "run_meta.json", meta)
    print(f"wrote {sub_path}  ({len(public)} keys, {len(processed)} processed)")

    if args.dry_run or args.no_score or not truth:
        return
    r_all = score_submission(public, truth)
    print_score(r_all, "full inbox — unscored emails default to GENERAL")
    r_sub = score_submission(public, truth, set(processed))
    print_score(r_sub, "processed emails only")
    save_json(out_dir / "score.json", {"full": r_all, "processed": r_sub})


if __name__ == "__main__":
    main()
