"""
report_service.py
-----------------
Handles persistence of audit and regression reports.
Saves structured JSON to the reports/ directory and
maintains a lightweight history index for the dashboard.
"""

import json
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

REPORTS_DIR = Path(__file__).parent.parent / "reports"
HISTORY_FILE = REPORTS_DIR / "_history.json"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


ReportType = Literal["audit", "regression"]


def _load_history() -> list[dict]:
    """Load the report history index from disk."""
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return []
    return []


def _save_history(history: list[dict]) -> None:
    """Persist the report history index to disk."""
    HISTORY_FILE.write_text(json.dumps(history, indent=2))


def save_report(
    report_data: dict,
    report_type: ReportType,
    original_filename: str,
) -> tuple[str, Path]:
    """
    Persist a report to disk and update the history index.

    Args:
        report_data:       The parsed report dict (audit or regression).
        report_type:       "audit" or "regression".
        original_filename: The user's original upload filename (for display).

    Returns:
        (report_id, json_path) — the unique report ID and path to the JSON file.
    """
    report_id = str(uuid.uuid4())[:8].upper()
    timestamp = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    payload = {
        "report_id": report_id,
        "report_type": report_type,
        "timestamp": timestamp,
        "original_filename": original_filename,
        "data": report_data,
    }

    json_path = REPORTS_DIR / f"{report_id}.json"
    json_path.write_text(json.dumps(payload, indent=2))
    logger.info("Report saved: %s -> %s", report_id, json_path)

    # Update history index (keep last 50 reports)
    history = _load_history()
    history.insert(0, {
        "report_id": report_id,
        "report_type": report_type,
        "timestamp": timestamp,
        "original_filename": original_filename,
        "score": report_data.get("score"),                  # audit only
        "verdict": report_data.get("overall_verdict"),      # regression only
        "finding_count": len(report_data.get("findings", [])),
        "change_count": len(report_data.get("changes", [])),
    })
    _save_history(history[:50])

    return report_id, json_path


def load_report(report_id: str) -> dict:
    """
    Load a full report payload by its ID.

    Returns:
        The full payload dict (including 'data' key).

    Raises:
        FileNotFoundError: If no report with that ID exists.
    """
    json_path = REPORTS_DIR / f"{report_id}.json"
    if not json_path.exists():
        raise FileNotFoundError(f"Report '{report_id}' not found.")
    return json.loads(json_path.read_text())


def get_history(limit: int = 20) -> list[dict]:
    """Return the most recent `limit` report summaries."""
    return _load_history()[:limit]


def delete_report(report_id: str) -> bool:
    """
    Remove a report from disk and history.

    Returns:
        True if deleted, False if not found.
    """
    json_path = REPORTS_DIR / f"{report_id}.json"
    if not json_path.exists():
        return False
    json_path.unlink()
    history = [h for h in _load_history() if h["report_id"] != report_id]
    _save_history(history)
    logger.info("Report deleted: %s", report_id)
    return True
