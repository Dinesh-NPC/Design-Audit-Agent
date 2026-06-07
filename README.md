# ◈ Design Audit Agent

> **AI-powered UI design auditor built with Google Gemini 2.5 Flash Vision.**

Accepts screenshots and returns structured, evidence-grounded design evaluations —
covering visual hierarchy, contrast, spacing, alignment, and consistency.  
Supports both single-image audits (Level 1) and before/after regression analysis (Level 2).

---

## Features

| | |
|---|---|
| **Level 1 — Design Audit** | Uploads one screenshot → AI analyses it against 5 design principles → returns severity-ranked findings with recommendations |
| **Level 2 — Regression Analysis** | Uploads before + after screenshots → AI detects every visual change → classifies as improvement / regression / neutral → flags accessibility regressions |
| **JSON Reports** | Every analysis saved as downloadable structured JSON |
| **Report History** | Lightweight index of last 50 reports, viewable in dashboard |
| **Modern UI** | Dark industrial dashboard with drag-and-drop uploads, confidence bars, severity badges, and loading animations |

---

## Project Structure

```
design_audit_agent/
├── app.py                      # Flask application & routes
├── agents/
│   ├── audit_agent.py          # Level 1 orchestration
│   └── regression_agent.py     # Level 2 orchestration
├── services/
│   ├── gemini_service.py       # Gemini API calls, prompts, retry logic
│   └── report_service.py       # Report persistence & history
├── templates/
│   ├── index.html              # Dashboard / upload forms
│   └── report.html             # Report display page
├── static/
│   ├── css/
│   │   ├── main.css            # Dashboard styles
│   │   └── report.css          # Report page styles
│   └── js/
│       └── main.js             # Upload, validation, history JS
├── uploads/                    # Uploaded screenshots (auto-created)
├── reports/                    # JSON report files (auto-created)
├── requirements.txt
├── .env.example
└── README.md
```

---

## Prerequisites

- Python 3.10 or higher
- A Google Gemini API key with access to `gemini-2.5-flash`

---

## Setup

### 1. Clone / Download

```bash
cd design_audit_agent
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate        # macOS / Linux
venv\Scripts\activate           # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and add your Gemini API key:

```
GEMINI_API_KEY=your_api_key_here
FLASK_SECRET_KEY=any_random_string
MAX_FILE_SIZE_MB=10
FLASK_ENV=development
```

Get your API key at: https://aistudio.google.com/app/apikey

---

## Running

### Development

```bash
python app.py
```

The app starts at **http://localhost:5000**

### Production (Gunicorn)

```bash
gunicorn -w 2 -b 0.0.0.0:5000 app:app
```

---

## Usage

### Level 1 — Single Screenshot Audit

1. Open **http://localhost:5000**
2. In **Card 1 (Single Screenshot Audit)**, drag-and-drop or click to upload a UI screenshot (PNG, JPG, or WebP, max 10 MB)
3. Click **Run Design Audit**
4. Wait 15–30 seconds while Gemini analyses the image
5. View the report with severity-ranked findings, confidence bars, and recommendations
6. Download the full JSON report

### Level 2 — Before / After Regression

1. Open **http://localhost:5000**
2. In **Card 2 (Before / After Comparison)**, upload a BEFORE and an AFTER screenshot
3. Click **Run Regression Analysis**
4. Wait 20–40 seconds
5. View the report with classified changes, accessibility flags, and an overall verdict
6. Download the full JSON report

### Report History

- Click **History** in the navbar to view recent reports
- Each entry links to the full report page

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Dashboard |
| `POST` | `/audit` | Run Level 1 design audit |
| `POST` | `/regression` | Run Level 2 regression analysis |
| `GET` | `/report/<id>` | View rendered report |
| `GET` | `/report/<id>/json` | Download JSON report |
| `GET` | `/history` | List recent reports (JSON) |
| `DELETE` | `/report/<id>` | Delete a report |

---

## Report Schema

### Level 1 — Audit

```json
{
  "summary": "...",
  "score": 72,
  "findings": [
    {
      "id": "F001",
      "principle": "Contrast",
      "severity": "high",
      "location": "Hero section CTA button",
      "observation": "Light grey text on white background...",
      "user_impact": "Users with low vision will struggle...",
      "recommendation": "Increase contrast ratio to at least 4.5:1",
      "confidence": 91
    }
  ],
  "positive_aspects": ["..."],
  "priority_fixes": ["..."]
}
```

### Level 2 — Regression

```json
{
  "changes": [
    {
      "id": "C001",
      "location": "Hero CTA",
      "change": "Button color changed from grey to blue",
      "classification": "improvement",
      "reasoning": "Higher contrast improves discoverability",
      "user_impact": "Improved CTA visibility for all users",
      "confidence": 94,
      "accessibility_flag": false,
      "change_type": "contrast"
    }
  ],
  "overall_verdict": "Net Improvement",
  "verdict_reasoning": "...",
  "change_counts": { "improvement": 4, "regression": 1, "neutral": 2 }
}
```

---

## Design Decisions

- **Low temperature (0.1)** on Gemini calls ensures deterministic, factual output
- **Retry logic** (3 attempts, exponential backoff) handles transient API errors
- **JSON extraction** handles markdown-fenced responses and malformed output gracefully
- **Evidence-only prompting** instructs the model to only report what is directly visible
- **Findings sorted** by severity then confidence for actionable output
- **Report history** stored as a lightweight JSON index (no database required)

---

## Limitations

- Requires a valid Gemini API key with quota
- Analysis quality depends on image resolution (higher-res screenshots yield better results)
- Gemini may occasionally misidentify element locations — confidence scores indicate certainty
- Not a replacement for professional WCAG auditing tools (e.g. axe, WAVE)

---

## License

MIT — free to use, modify, and distribute.
