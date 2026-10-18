"""Read the saved validation report (cached by file modification time)."""
from __future__ import annotations

import json

from src.validation.report import REPORT_PATH

_cache: dict = {"mtime": None, "data": None}


def load_report() -> dict | None:
    try:
        mtime = REPORT_PATH.stat().st_mtime
    except FileNotFoundError:
        return None
    if _cache["mtime"] != mtime:
        try:
            _cache["data"] = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
            _cache["mtime"] = mtime
        except (ValueError, OSError):
            return None
    return _cache["data"]


def status_map() -> dict:
    """{model_key: {status, status_label, summary}} -- empty when no report has been generated."""
    report = load_report()
    if not report:
        return {}
    return {i["key"]: {"status": i["status"], "status_label": i["status_label"], "summary": i["summary"]} for i in report.get("registry", [])}
