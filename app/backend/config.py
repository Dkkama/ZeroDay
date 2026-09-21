from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

DATA_V2 = ROOT / "sdoc-hackathon-docker" / "data_v2"
FLASH_SUBMISSION = ROOT / "sdoc_eval" / "outputs" / "flash25_v2" / "submission.json"
FLASH_SCORE = ROOT / "sdoc_eval" / "outputs" / "flash25_v2" / "score.json"
PROMPT_PATH = ROOT / "sdoc_eval" / "prompts" / "v1.md"
STATE_PATH = Path(__file__).resolve().parent / "data" / "state.json"
UPLOAD_DIR = Path(__file__).resolve().parent / "data" / "uploads"

DEMO_EMAIL = os.environ.get("DEMO_EMAIL", "clerk@zeroday.local")
DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "clerk123")
SESSION_SECRET = os.environ.get("SESSION_SECRET", "zeroday-dev-secret")

GCP_PROJECT = os.environ.get("GCP_PROJECT", "hackathon-2026-509207")
STORE_BACKEND = os.environ.get("STORE_BACKEND", "json").strip().lower()
VERTEX_LOCATION = os.environ.get("VERTEX_LOCATION", "global")
VERTEX_MODEL = os.environ.get("VERTEX_MODEL", "gemini-3-flash-preview")
CURSOR_MODEL = os.environ.get("CURSOR_MODEL", "gemini-3-flash")

VERTEX_MAX_BATCH = int(os.environ.get("VERTEX_MAX_BATCH", "2048"))
CRON_SECRET = os.environ.get("CRON_SECRET", "")

COMPARE_FIELDS = [
    "shipper",
    "consignee",
    "notify_party",
    "port_of_loading",
    "port_of_discharge",
    "container_count",
    "gross_weight_kg",
]

CATEGORY_META = {
    "BL_COMPARISON": {
        "label": "Requests to check documents",
        "color": "#e11d48",
    },
    "SI_REQUEST": {
        "label": "Prepare new shipping instructions",
        "color": "#2563eb",
    },
    "INVOICE_QUERY": {
        "label": "Answer invoice questions",
        "color": "#d97706",
    },
    "GENERAL": {
        "label": "Share operational updates",
        "color": "#0f766e",
    },
    "SPAM": {
        "label": "Spam / junk",
        "color": "#6b7280",
    },
}

EMPTY_FIELDS = {name: "" for name in COMPARE_FIELDS}
