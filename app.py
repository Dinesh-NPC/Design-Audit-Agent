"""
app.py
------
Design Audit Agent — Flask Application Entry Point.

Routes:
  GET  /                         → Dashboard / upload forms
  POST /audit                    → Level 1: single image audit
  POST /regression               → Level 2: before/after regression
  GET  /report/<report_id>       → View rendered report
  GET  /report/<report_id>/json  → Download raw JSON
  GET  /history                  → Report history list (JSON)
  DELETE /report/<report_id>     → Delete a report
"""

import os
import uuid
import logging
from pathlib import Path

from flask import (
    Flask,
    request,
    render_template,
    jsonify,
    redirect,
    url_for,
    send_file,
    abort,
)
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# ── Project imports (agents + services) ───────────────────────────────────────
from agents.audit_agent import run_audit
from agents.regression_agent import run_regression
from services.report_service import load_report, get_history, delete_report, REPORTS_DIR

# ── Bootstrap ─────────────────────────────────────────────────────────────────
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", os.urandom(32).hex())

# ── Configuration ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
MAX_FILE_SIZE_BYTES = int(os.getenv("MAX_FILE_SIZE_MB", "10")) * 1024 * 1024

app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE_BYTES


# ── Helpers ────────────────────────────────────────────────────────────────────

def _allowed(filename: str) -> bool:
    """Return True if file extension is in the allowed set."""
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def _save_upload(file_storage) -> tuple[str, str]:
    """
    Validate and save an uploaded FileStorage to the uploads directory.

    Returns:
        (saved_path, original_filename)

    Raises:
        ValueError: If validation fails.
    """
    if not file_storage or file_storage.filename == "":
        raise ValueError("No file selected.")
    if not _allowed(file_storage.filename):
        raise ValueError(
            "Unsupported file type. Please upload PNG, JPG, or WebP."
        )

    original = secure_filename(file_storage.filename)
    unique_name = f"{uuid.uuid4().hex}_{original}"
    save_path = UPLOAD_DIR / unique_name
    file_storage.save(str(save_path))
    logger.info("Saved upload: %s (%d bytes)", save_path, save_path.stat().st_size)
    return str(save_path), original


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Homepage with audit and regression upload forms."""
    return render_template("index.html")


@app.route("/audit", methods=["POST"])
def audit():
    """
    Level 1: Accept a single screenshot and return a design audit report.
    Redirects to the report view on success; returns JSON error on failure.
    """
    try:
        file = request.files.get("screenshot")
        image_path, original_name = _save_upload(file)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        report_id, _ = run_audit(image_path, original_name)
        return redirect(url_for("view_report", report_id=report_id))
    except Exception as exc:
        logger.exception("Audit failed for %s", original_name)
        return jsonify({"error": f"Analysis failed: {exc}"}), 500


@app.route("/regression", methods=["POST"])
def regression():
    """
    Level 2: Accept before + after screenshots and return regression analysis.
    Redirects to the report view on success; returns JSON error on failure.
    """
    try:
        before = request.files.get("before_screenshot")
        after = request.files.get("after_screenshot")
        before_path, before_name = _save_upload(before)
        after_path, after_name = _save_upload(after)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        report_id, _ = run_regression(
            before_path, after_path, before_name, after_name
        )
        return redirect(url_for("view_report", report_id=report_id))
    except Exception as exc:
        logger.exception("Regression analysis failed")
        return jsonify({"error": f"Analysis failed: {exc}"}), 500


@app.route("/report/<report_id>")
def view_report(report_id: str):
    """Render the human-readable report page."""
    try:
        payload = load_report(report_id)
    except FileNotFoundError:
        abort(404)

    return render_template(
        "report.html",
        report_id=report_id,
        report_type=payload["report_type"],
        timestamp=payload["timestamp"],
        original_filename=payload["original_filename"],
        data=payload["data"],
    )


@app.route("/report/<report_id>/json")
def download_json(report_id: str):
    """Serve the raw JSON report as a file download."""
    json_path = REPORTS_DIR / f"{report_id}.json"
    if not json_path.exists():
        abort(404)
    return send_file(
        str(json_path),
        as_attachment=True,
        download_name=f"design_audit_{report_id}.json",
        mimetype="application/json",
    )


@app.route("/history")
def history():
    """Return JSON list of recent reports (used by dashboard history panel)."""
    return jsonify(get_history(limit=20))


@app.route("/report/<report_id>", methods=["DELETE"])
def remove_report(report_id: str):
    """Delete a report by ID."""
    deleted = delete_report(report_id)
    if not deleted:
        abort(404)
    return jsonify({"deleted": report_id})


# ── Error Handlers ─────────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(_):
    return render_template("index.html"), 404


@app.errorhandler(413)
def too_large(_):
    max_mb = int(os.getenv("MAX_FILE_SIZE_MB", "10"))
    return jsonify({"error": f"File too large. Maximum allowed size is {max_mb} MB."}), 413


@app.errorhandler(500)
def server_error(exc):
    logger.error("Internal server error: %s", exc)
    return jsonify({"error": "An internal error occurred. Check server logs."}), 500


# ── Entry Point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_ENV", "production") == "development"
    logger.info("Starting Design Audit Agent on port %d (debug=%s)", port, debug)
    app.run(host="0.0.0.0", port=port, debug=debug)
