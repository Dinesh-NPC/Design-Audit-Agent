"""
regression_agent.py
--------------------
Level 2 Agent — Before/After Visual Regression Analysis.
Orchestrates dual-image upload validation, Gemini analysis,
post-processing, and report persistence.
"""

import logging
from services.gemini_service import run_regression_analysis
from services.report_service import save_report

logger = logging.getLogger(__name__)

# UI metadata maps
CLASSIFICATION_COLORS = {
    "improvement": "success",
    "regression": "danger",
    "neutral": "secondary",
}

CLASSIFICATION_ICONS = {
    "improvement": "bi-arrow-up-circle-fill",
    "regression": "bi-arrow-down-circle-fill",
    "neutral": "bi-dash-circle-fill",
}

CHANGE_TYPE_ICONS = {
    "contrast": "bi-circle-half",
    "spacing": "bi-distribute-vertical",
    "typography": "bi-type",
    "color": "bi-palette",
    "layout": "bi-layout-wtf",
    "content": "bi-file-text",
    "icon": "bi-emoji-smile",
    "other": "bi-three-dots",
}

VERDICT_CONFIG = {
    "Net Improvement": {"color": "success", "icon": "bi-graph-up-arrow"},
    "Net Regression": {"color": "danger", "icon": "bi-graph-down-arrow"},
    "Neutral": {"color": "secondary", "icon": "bi-dash-lg"},
}


def _enrich_changes(changes: list[dict]) -> list[dict]:
    """
    Add UI metadata to each change entry and normalise required fields.
    """
    enriched = []
    for i, c in enumerate(changes):
        classification = c.get("classification", "neutral").lower()
        confidence = int(c.get("confidence", 70))
        confidence = max(0, min(100, confidence))
        change_type = c.get("change_type", "other").lower()

        enriched.append({
            "id": c.get("id", f"C{i+1:03d}"),
            "location": c.get("location", "Unknown location"),
            "change": c.get("change", ""),
            "classification": classification,
            "classification_color": CLASSIFICATION_COLORS.get(classification, "secondary"),
            "classification_icon": CLASSIFICATION_ICONS.get(classification, "bi-circle"),
            "reasoning": c.get("reasoning", ""),
            "user_impact": c.get("user_impact", ""),
            "confidence": confidence,
            "accessibility_flag": bool(c.get("accessibility_flag", False)),
            "change_type": change_type,
            "change_type_icon": CHANGE_TYPE_ICONS.get(change_type, "bi-three-dots"),
        })

    # Sort: regressions first (most critical), then improvements, then neutral
    order_map = {"regression": 0, "improvement": 1, "neutral": 2}
    enriched.sort(key=lambda x: (order_map.get(x["classification"], 9), -x["confidence"]))
    return enriched


def run_regression(
    before_path: str,
    after_path: str,
    before_filename: str,
    after_filename: str,
) -> tuple[str, dict]:
    """
    Full Level 2 pipeline:
      1. Call Gemini vision API for regression analysis.
      2. Enrich changes with UI metadata.
      3. Save report to disk.
      4. Return (report_id, enriched_report).

    Args:
        before_path:      Path to the 'before' image on disk.
        after_path:       Path to the 'after' image on disk.
        before_filename:  User-facing 'before' filename.
        after_filename:   User-facing 'after' filename.

    Returns:
        (report_id, report_dict)
    """
    logger.info(
        "RegressionAgent: starting analysis. before=%s after=%s",
        before_filename, after_filename
    )

    # ── Step 1: Gemini analysis ────────────────────────────────────────────────
    raw_report = run_regression_analysis(before_path, after_path)

    # ── Step 2: Enrich & normalise ────────────────────────────────────────────
    changes = _enrich_changes(raw_report.get("changes", []))
    verdict = raw_report.get("overall_verdict", "Neutral")
    verdict_cfg = VERDICT_CONFIG.get(verdict, VERDICT_CONFIG["Neutral"])

    enriched = {
        "changes": changes,
        "accessibility_regressions": raw_report.get("accessibility_regressions", []),
        "improvements_summary": raw_report.get("improvements_summary", ""),
        "regressions_summary": raw_report.get("regressions_summary", ""),
        "overall_verdict": verdict,
        "verdict_color": verdict_cfg["color"],
        "verdict_icon": verdict_cfg["icon"],
        "verdict_reasoning": raw_report.get("verdict_reasoning", ""),
        "change_counts": raw_report.get("change_counts", {}),
        "total_changes": len(changes),
        "before_filename": before_filename,
        "after_filename": after_filename,
        # Flag if any a11y regressions were detected
        "has_a11y_regressions": bool(raw_report.get("accessibility_regressions")),
    }

    # ── Step 3: Persist ────────────────────────────────────────────────────────
    label = f"{before_filename} → {after_filename}"
    report_id, _ = save_report(enriched, "regression", label)

    logger.info(
        "RegressionAgent: complete. report_id=%s verdict=%s changes=%d",
        report_id, verdict, len(changes)
    )
    return report_id, enriched
