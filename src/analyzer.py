"""
analyzer.py — Module 3
Sends code files to Cerebras (Llama 3.3 70B) for analysis.
Falls back to Groq automatically if Cerebras fails.
"""

import json
from cerebras.cloud.sdk import Cerebras
from groq import Groq
from config import CEREBRAS_API_KEY, GROQ_API_KEY, MIN_CONFIDENCE


cerebras_client = Cerebras(api_key=CEREBRAS_API_KEY)
groq_client     = Groq(api_key=GROQ_API_KEY)


SYSTEM_PROMPT = """You are a senior software engineer doing a careful code review.
Your job is to find real, reproducible bugs and security issues only.

You must respond ONLY with a valid JSON object — no explanation, no markdown, no backticks.

{
  "findings": [
    {
      "type": "bug" | "security",
      "severity": "critical" | "high" | "medium" | "low",
      "confidence": <float between 0.0 and 1.0>,
      "line_reference": "<function or line where issue is>",
      "title": "<short one-line title>",
      "description": "<clear explanation of what is wrong and why it matters>",
      "fix": "<concrete fix>"
    }
  ]
}

STRICT RULES — read carefully:
- Only report "bug" or "security" type findings. Never report performance or suggestions.
- Only report confidence >= 0.90. If you are not certain, do not include it.
- NEVER flag stdin size limits, sync fs calls, or event loop blocking in short-lived CLI scripts or one-shot processes. These are not real issues in that context.
- NEVER flag environment variables as security issues if they are local config on the user's own machine.
- NEVER flag missing radix in parseInt, missing error handling, or other style/best-practice issues.
- NEVER report a finding based on truncated code. If the file appears cut off, ignore anything near the truncation point.
- Before reporting a bug, ask yourself: does this cause a real, observable failure in normal use? If not, skip it.
- Max 2 findings per file. If the code looks clean or you are unsure, return { "findings": [] }"""


def build_user_prompt(file_path: str, language: str, content: str) -> str:
    return f"""Analyze this {language} file for bugs, security vulnerabilities, and performance issues.

File: {file_path}

```{language.lower()}
{content}
```"""


def call_llm(messages: list[dict]) -> str:
    """
    Tries Cerebras first. If it fails for any reason
    (rate limit, timeout, outage), automatically falls back to Groq.
    Both use Llama 3.3 70B — same model quality.
    """

    # ── Try Cerebras ────────────────────────────────────────
    try:
        response = cerebras_client.chat.completions.create(
            model="gpt-oss-120b",
            messages=messages,
            max_tokens=1500,
            temperature=0.1,
        )
        print("[Analyzer] Provider: Cerebras ✅")
        return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"[Analyzer] Cerebras failed → {e}")
        print("[Analyzer] Falling back to Groq...")

    # ── Fallback: Groq ───────────────────────────────────────
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=1500,
            temperature=0.1,
        )
        print("[Analyzer] Provider: Groq ✅ (fallback)")
        return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"[Analyzer] Groq also failed → {e}")
        raise RuntimeError("Both Cerebras and Groq failed.") from e


def analyze_file(file: dict) -> list[dict]:
    """
    Analyzes a single file dict { path, language, content }.
    Returns a list of finding dicts (may be empty if code is clean).
    """
    path     = file["path"]
    language = file["language"]
    content  = file["content"]

    print(f"[Analyzer] Analyzing {path} [{language}]...")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": build_user_prompt(path, language, content)},
    ]

    try:
        raw_text = call_llm(messages)

        # Strip markdown code fences if model adds them anyway
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        raw_text = raw_text.strip()

        parsed   = json.loads(raw_text)
        findings = parsed.get("findings", [])

        # Filter by confidence as a safety net
        filtered = [f for f in findings if f.get("confidence", 0) >= MIN_CONFIDENCE]

        # Attach file context to each finding
        for finding in filtered:
            finding["file_path"] = path
            finding["language"]  = language

        print(f"[Analyzer]   → {len(filtered)} finding(s) above confidence threshold.")
        return filtered

    except json.JSONDecodeError as e:
        print(f"[Analyzer] ERROR: Could not parse JSON response for {path} → {e}")
        return []
    except RuntimeError:
        # Both providers failed — skip this file gracefully
        return []
    except Exception as e:
        print(f"[Analyzer] ERROR analyzing {path} → {e}")
        return []


def analyze_repo(files: list[dict]) -> list[dict]:
    """
    Analyzes all files in a repo.
    Returns combined list of all findings across all files.
    """
    all_findings = []

    for file in files:
        findings = analyze_file(file)
        all_findings.extend(findings)

    # Sort by severity so critical issues come first
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    all_findings.sort(key=lambda f: severity_order.get(f.get("severity", "low"), 3))

    print(f"\n[Analyzer] Total findings across all files: {len(all_findings)}")
    return all_findings


# ── Quick test ───────────────────────────────────────────────
if __name__ == "__main__":
    test_file = {
        "path":     "app.py",
        "language": "Python",
        "content":  """
import sqlite3

def get_user(username):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    query = f"SELECT * FROM users WHERE username = '{username}'"
    cursor.execute(query)
    return cursor.fetchone()

def read_config():
    secret_key  = "hardcoded_secret_key_12345"
    db_password = "admin123"
    return secret_key, db_password
""",
    }

    findings = analyze_file(test_file)
    print("\n── Findings ──────────────────────────────")
    for f in findings:
        print(f"\n  [{f['severity'].upper()}] {f['title']}")
        print(f"  Confidence: {f['confidence']} | File: {f['file_path']}")
        print(f"  Problem: {f['description']}")
        print(f"  Fix: {f['fix']}")
