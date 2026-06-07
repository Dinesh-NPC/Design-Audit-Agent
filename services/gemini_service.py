"""
gemini_service.py
-----------------
Core service layer for all Google Gemini API interactions.
Handles image encoding, prompt construction, API calls,
retry logic, and JSON parsing for both audit modes.
"""

import os
import json
import time
import base64
import logging
from pathlib import Path
from typing import Optional

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
MODEL_ID = "gemini-2.5-flash"
MAX_RETRIES = 3
RETRY_DELAY_SEC = 2
MAX_OUTPUT_TOKENS = 8192


def _get_client() -> genai.Client:
    """Instantiate and return a Gemini client from the env API key."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY is not set. "
            "Copy .env.example to .env and add your key."
        )
    return genai.Client(api_key=api_key)


def _encode_image(image_path: str) -> tuple[str, str]:
    """
    Read an image file and return (base64_data, mime_type).
    Supports PNG, JPEG/JPG, and WebP.
    """
    path = Path(image_path)
    suffix = path.suffix.lower()
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }
    mime_type = mime_map.get(suffix, "image/png")
    with open(image_path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")
    return data, mime_type


def _parse_json_response(raw_text: str) -> dict:
    """
    Robustly extract a JSON object from the model's raw text output.
    Strips markdown fences, leading/trailing whitespace, and falls
    back to scanning for the first '{' if needed.
    """
    text = raw_text.strip()

    # Strip ```json ... ``` or ``` ... ``` fences
    if text.startswith("```"):
        lines = text.split("\n")
        # drop first and last fence lines
        inner = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(inner).strip()

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Scan for the first '{' and last '}' as a recovery attempt
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not extract valid JSON from model response:\n{text[:500]}")


def _call_gemini(client: genai.Client, contents: list) -> str:
    """
    Make a single API call with retry logic on transient errors.
    Returns the text of the first candidate response.
    """
    config = types.GenerateContentConfig(
        max_output_tokens=MAX_OUTPUT_TOKENS,
        temperature=0.1,   # Low temperature for deterministic, factual output
    )

    last_error: Optional[Exception] = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=MODEL_ID,
                contents=contents,
                config=config,
            )
            return response.text
        except Exception as exc:
            last_error = exc
            logger.warning(
                "Gemini API attempt %d/%d failed: %s",
                attempt, MAX_RETRIES, exc
            )
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SEC * attempt)

    raise RuntimeError(
        f"Gemini API failed after {MAX_RETRIES} attempts. "
        f"Last error: {last_error}"
    )


# ── Level 1: Single-image Design Audit ────────────────────────────────────────

AUDIT_SYSTEM_PROMPT = """You are a world-class UX/UI design auditor with 15+ years of experience.
Your job is to evaluate a UI screenshot against fundamental design principles.

CRITICAL RULES:
- Only report issues you can DIRECTLY OBSERVE in the image. No speculation.
- Be specific about LOCATION (e.g., "top navigation bar", "hero section CTA button").
- Every finding must be grounded in visible evidence.
- Minimize hallucinations: if you cannot see it clearly, do not report it.
- Identify at LEAST 3 issues, up to 10.

DESIGN PRINCIPLES TO EVALUATE:
1. Visual Hierarchy – Is there a clear focal point? Does the layout guide the eye logically?
2. Contrast – Are text/background contrast ratios sufficient? (WCAG AA = 4.5:1 for normal text)
3. Spacing – Is there consistent padding/margin? Breathing room between elements?
4. Alignment – Are elements aligned on a consistent grid? Any orphaned elements?
5. Consistency – Are fonts, colors, button styles, and icon sizes uniform throughout?

SEVERITY LEVELS:
- critical: Blocks user task completion or causes severe accessibility failure
- high: Significantly degrades usability or readability
- medium: Noticeable issue that affects experience but user can still complete tasks
- low: Minor polish issue
- info: Observation or positive note

OUTPUT FORMAT — respond with ONLY valid JSON, no markdown fences, no extra text:
{
  "summary": "2-3 sentence overall design assessment",
  "score": <integer 0-100, overall design quality>,
  "findings": [
    {
      "id": "F001",
      "principle": "<Visual Hierarchy|Contrast|Spacing|Alignment|Consistency>",
      "severity": "<critical|high|medium|low|info>",
      "location": "<specific location on the page>",
      "observation": "<what you see — the factual evidence>",
      "user_impact": "<how this affects the end user>",
      "recommendation": "<specific, actionable fix>",
      "confidence": <integer 0-100>
    }
  ],
  "positive_aspects": ["<list of things done well>"],
  "priority_fixes": ["<top 3 most impactful fixes as strings>"]
}"""


def run_design_audit(image_path: str) -> dict:
    """
    Level 1: Analyse a single UI screenshot and return a structured
    design audit report as a Python dict.

    Args:
        image_path: Absolute or relative path to the uploaded image.

    Returns:
        Parsed audit report dict matching the schema in AUDIT_SYSTEM_PROMPT.

    Raises:
        RuntimeError: On API failure after all retries.
        ValueError: If the model response cannot be parsed as JSON.
    """
    logger.info("Starting design audit for: %s", image_path)
    client = _get_client()

    img_data, mime_type = _encode_image(image_path)

    user_message = (
        "Please perform a thorough design audit of this UI screenshot. "
        "Identify every design issue you can observe directly in the image. "
        "Return ONLY the JSON object as specified — no markdown, no extra commentary."
    )

    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part(text=AUDIT_SYSTEM_PROMPT),
                types.Part(
                    inline_data=types.Blob(mime_type=mime_type, data=img_data)
                ),
                types.Part(text=user_message),
            ],
        )
    ]

    raw = _call_gemini(client, contents)
    result = _parse_json_response(raw)

    # Ensure required keys exist with safe defaults
    result.setdefault("summary", "Audit completed.")
    result.setdefault("score", 50)
    result.setdefault("findings", [])
    result.setdefault("positive_aspects", [])
    result.setdefault("priority_fixes", [])

    logger.info(
        "Audit complete. %d findings, score: %s",
        len(result["findings"]), result["score"]
    )
    return result


# ── Level 2: Before/After Regression Analysis ─────────────────────────────────

REGRESSION_SYSTEM_PROMPT = """You are an expert UI/UX regression analyst.
You will receive TWO UI screenshots: a BEFORE image and an AFTER image.
Your job is to identify ALL visual differences and classify each change.

CRITICAL RULES:
- Only report differences you can DIRECTLY OBSERVE by comparing the two images.
- Be specific about LOCATION and WHAT changed (not just that it changed).
- You must identify at LEAST 5 distinct differences.
- Flag any accessibility regressions (contrast reductions, removed labels, smaller text).
- Explicitly mention contrast changes, spacing reductions, and readability issues.

CLASSIFICATION:
- improvement: Change benefits usability, accessibility, clarity, or aesthetics
- regression: Change harms usability, accessibility, clarity, or aesthetics
- neutral: Change is cosmetic with no clear positive or negative impact

OVERALL VERDICT:
- "Net Improvement": More/weightier improvements than regressions
- "Net Regression": More/weightier regressions than improvements
- "Neutral": Roughly balanced or all neutral changes

OUTPUT FORMAT — respond with ONLY valid JSON, no markdown fences, no extra text:
{
  "changes": [
    {
      "id": "C001",
      "location": "<specific UI location>",
      "change": "<concise description of what changed>",
      "classification": "<improvement|regression|neutral>",
      "reasoning": "<why you classified it this way>",
      "user_impact": "<effect on end user experience>",
      "confidence": <integer 0-100>,
      "accessibility_flag": <true|false>,
      "change_type": "<contrast|spacing|typography|color|layout|content|icon|other>"
    }
  ],
  "accessibility_regressions": ["<list of any accessibility concerns>"],
  "improvements_summary": "<summary of improvements>",
  "regressions_summary": "<summary of regressions>",
  "overall_verdict": "<Net Improvement|Net Regression|Neutral>",
  "verdict_reasoning": "<explanation of overall verdict>",
  "change_counts": {
    "improvement": <int>,
    "regression": <int>,
    "neutral": <int>
  }
}"""


def run_regression_analysis(before_path: str, after_path: str) -> dict:
    """
    Level 2: Compare two UI screenshots (before/after) and return a
    structured regression analysis report.

    Args:
        before_path: Path to the 'before' screenshot.
        after_path: Path to the 'after' screenshot.

    Returns:
        Parsed regression report dict matching REGRESSION_SYSTEM_PROMPT schema.

    Raises:
        RuntimeError: On API failure after all retries.
        ValueError: If the model response cannot be parsed as JSON.
    """
    logger.info(
        "Starting regression analysis: before=%s, after=%s",
        before_path, after_path
    )
    client = _get_client()

    before_data, before_mime = _encode_image(before_path)
    after_data, after_mime = _encode_image(after_path)

    user_message = (
        "Here are two UI screenshots.\n"
        "IMAGE 1 is the BEFORE state.\n"
        "IMAGE 2 is the AFTER state.\n\n"
        "Compare them carefully and identify every visual difference. "
        "Return ONLY the JSON object as specified — no markdown, no extra commentary."
    )

    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part(text=REGRESSION_SYSTEM_PROMPT),
                types.Part(text="IMAGE 1 — BEFORE:"),
                types.Part(
                    inline_data=types.Blob(mime_type=before_mime, data=before_data)
                ),
                types.Part(text="IMAGE 2 — AFTER:"),
                types.Part(
                    inline_data=types.Blob(mime_type=after_mime, data=after_data)
                ),
                types.Part(text=user_message),
            ],
        )
    ]

    raw = _call_gemini(client, contents)
    result = _parse_json_response(raw)

    # Safe defaults
    result.setdefault("changes", [])
    result.setdefault("accessibility_regressions", [])
    result.setdefault("improvements_summary", "")
    result.setdefault("regressions_summary", "")
    result.setdefault("overall_verdict", "Neutral")
    result.setdefault("verdict_reasoning", "")
    result.setdefault(
        "change_counts", {"improvement": 0, "regression": 0, "neutral": 0}
    )

    # Recompute change_counts from actual data to avoid model mistakes
    counts = {"improvement": 0, "regression": 0, "neutral": 0}
    for c in result["changes"]:
        key = c.get("classification", "neutral").lower()
        if key in counts:
            counts[key] += 1
    result["change_counts"] = counts

    logger.info(
        "Regression analysis complete. %d changes detected. Verdict: %s",
        len(result["changes"]), result["overall_verdict"]
    )
    return result
