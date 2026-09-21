from __future__ import annotations

import re

from config import COMPARE_FIELDS, EMPTY_FIELDS

LABELS = {
    "shipper": [
        r"shipper\s*\(principal[^\)]*\)",
        r"shipper/exporter",
        r"shipper\s*\(发货人\)",
        r"shipper",
    ],
    "consignee": [
        r"consignee\s*\(non-negotiable\)",
        r"consignee\s*\(收货人\)",
        r"to the order of",
        r"consignee",
    ],
    "notify_party": [
        r"notify party/intermediate consignee",
        r"notify party\s*\(通知人\)",
        r"notify party",
        r"notify",
    ],
    "port_of_loading": [
        r"port of loading\s*\(pol\)",
        r"port of loading",
        r"load port",
        r"pol\s*\(装货港\)",
        r"\bpol\b",
        r"port of loading",
    ],
    "port_of_discharge": [
        r"port of discharge\s*\(pod\)",
        r"port of discharge",
        r"discharge port",
        r"pod\s*\(卸货港\)",
        r"\bpod\b",
    ],
    "container_count": [
        r"no\.\s*of containers or packages",
        r"no\.\s*of containers",
        r"total containers",
        r"container count",
        r"箱数",
    ],
    "gross_weight_kg": [
        r"gross weight毛重\(kgs\)",
        r"gross wt\s*\(kgs\)",
        r"gross weight\s*\(kg\)",
        r"gross weight",
        r"gross wt",
        r"毛重",
    ],
}


def extract_fields(text: str) -> dict:
    out = dict(EMPTY_FIELDS)
    if not text:
        return out
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines() if ln.strip()]
    joined = "\n".join(lines)
    for field, patterns in LABELS.items():
        value = _match_field(joined, lines, patterns)
        if value:
            out[field] = _clean_value(field, value)
    return out


def _match_field(joined: str, lines: list[str], patterns: list[str]) -> str:
    for pat in patterns:
        rx = re.compile(rf"(?im)(?:^|\n|[|])\s*(?:{pat})\s*[:|]?\s*(.+)")
        m = rx.search(joined)
        if not m:
            continue
        raw = m.group(1).strip()
        raw = raw.split("\n")[0].strip()
        if "|" in raw:
            raw = raw.split("|")[0].strip()
        if raw and not _looks_like_label(raw):
            return raw
    for line in lines:
        lower = line.lower()
        for pat in patterns:
            if re.search(pat, lower):
                if "|" in line:
                    parts = [p.strip() for p in line.split("|") if p.strip()]
                    if len(parts) >= 2:
                        return parts[1]
                if ":" in line:
                    return line.split(":", 1)[1].strip()
    return ""


def _looks_like_label(value: str) -> bool:
    compact = re.sub(r"[^a-z]", "", value.lower())
    return compact in {
        "shipper", "consignee", "notifyparty", "portofloading",
        "portofdischarge", "containercount", "grossweight",
    }


def _clean_value(field: str, value: str) -> str:
    value = value.strip(" :-|")
    value = re.sub(r"\s+", " ", value)
    if field == "container_count":
        m = re.search(r"(\d+)", value)
        return m.group(1) if m else value
    if field == "gross_weight_kg":
        compact = value.replace(",", "").replace(" ", "")
        m = re.search(r"(\d+(?:\.\d+)?)", compact)
        return m.group(1) if m else value
    return value


def empty_fields() -> dict:
    return dict(EMPTY_FIELDS)


def field_state(si_val: str, bl_val: str, resolved: str | None) -> dict:
    si_val = (si_val or "").strip()
    bl_val = (bl_val or "").strip()
    resolved = (resolved or "").strip()
    if resolved:
        source = "custom"
        if resolved == si_val:
            source = "si"
        elif resolved == bl_val:
            source = "bl"
        return {"si": si_val, "bl": bl_val, "value": resolved, "source": source, "empty": False}
    if not si_val and not bl_val:
        return {"si": "", "bl": "", "value": "", "source": None, "empty": True}
    if si_val and bl_val and si_val.casefold() == bl_val.casefold():
        return {"si": si_val, "bl": bl_val, "value": si_val, "source": "both", "empty": False}
    if si_val and not bl_val:
        return {"si": si_val, "bl": "", "value": si_val, "source": "si", "empty": False}
    if bl_val and not si_val:
        return {"si": "", "bl": bl_val, "value": bl_val, "source": "bl", "empty": False}
    return {"si": si_val, "bl": bl_val, "value": "", "source": None, "empty": False}
