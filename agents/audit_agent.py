"""
audit_agent.py
--------------
Level 1 Agent — Single Screenshot Design Audit.
Orchestrates upload validation, Gemini analysis,
post-processing, and report persistence.
"""

import logging
from pathlib import Path

from services.gemini_service import run_design_audit
from services.report_service import save_report

logger = logging.getLogger(__name__)

# Severity ordering for sorting findings
SEVERITY_ORDER = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "info": 4,
}

# Color classes mapped to severity (for template rendering)
SEVERITY_COLORS = {
    "critical": "danger",
    "high": "warning",
    "medium": "info",
    "low": "secondary",
    "info": "success",
}

PRINCIPLE_ICONS = {
    "Visual Hierarchy": "bi-layers",
    "Contrast": "bi-circle-half",
    "Spacing": "bi-distribute-vertical",
    "Alignment": "bi-layout-text-sidebar",
    "Consistency": "bi-grid-3x3",
}


def _enrich_findings(findings: list[dict]) -> list[dict]:
    """
    Enrich each finding with UI metadata (color class, icon, etc.)
    and ensure required fields are present with safe defaults.
    """
    enriched = []
    for i, f in enumerate(findings):
        principle = f.get("principle", "General")
        severity = f.get("severity", "medium").lower()
        confidence = int(f.get("confidence", 70))
        confidence = max(0, min(100, confidence))  # clamp 0-100

        enriched.append({
            "id": f.get("id", f"F{i+1:03d}"),
            "principle": principle,
            "severity": severity,
            "severity_color": SEVERITY_COLORS.get(severity, "secondary"),
            "severity_order": SEVERITY_ORDER.get(severity, 99),
            "location": f.get("location", "Unknown location"),
            "observation": f.get("observation", ""),
            "user_impact": f.get("user_impact", ""),
            "recommendation": f.get("recommendation", ""),
            "confidence": confidence,
            "icon": PRINCIPLE_ICONS.get(principle, "bi-exclamation-circle"),
        })

    # Sort by severity then by confidence (desc)
    enriched.sort(key=lambda x: (x["severity_order"], -x["confidence"]))
    return enriched


def _build_severity_counts(findings: list[dict]) -> dict:
    """Count findings per severity level."""
    counts = {k: 0 for k in SEVERITY_ORDER}
    for f in findings:
        sev = f.get("severity", "medium")
        if sev in counts:
            counts[sev] += 1
    return counts


def run_audit(image_path: str, original_filename: str) -> tuple[str, dict]:
    """
    Full Level 1 pipeline:
      1. Call Gemini vision API for design audit.
      2. Enrich findings with UI metadata.
      3. Save report to disk.
      4. Return (report_id, enriched_report).

    Args:
        image_path:        Path to the uploaded image on disk.
        original_filename: User-facing filename for display/history.

    Returns:
        (report_id, report_dict)
    """
    logger.info("AuditAgent: starting audit for %s", original_filename)

    # ── Step 1: Gemini analysis ────────────────────────────────────────────────
    raw_report = run_design_audit(image_path)

    # ── Step 2: Enrich & normalize ────────────────────────────────────────────
    findings = _enrich_findings(raw_report.get("findings", []))
    score = int(raw_report.get("score", 50))
    score = max(0, min(100, score))

    # Score color for UI
    if score >= 75:
        score_color = "success"
    elif score >= 50:
        score_color = "warning"
    else:
        score_color = "danger"

    enriched = {
        "summary": raw_report.get("summary", ""),
        "score": score,
        "score_color": score_color,
        "findings": findings,
        "severity_counts": _build_severity_counts(findings),
        "positive_aspects": raw_report.get("positive_aspects", []),
        "priority_fixes": raw_report.get("priority_fixes", []),
        "total_findings": len(findings),
    }

    # ── Step 3: Persist ────────────────────────────────────────────────────────
    report_id, _ = save_report(enriched, "audit", original_filename)

    logger.info("AuditAgent: complete. report_id=%s score=%d", report_id, score)
    return report_id, enriched
