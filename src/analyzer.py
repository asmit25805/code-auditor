"""
analyzer.py — Module 3
Sends code files to Cerebras for analysis.
Falls back to Groq → Gemini automatically if each provider fails.
Uses double-pass validation: only keeps findings that appear in both passes.
"""

import json
from cerebras.cloud.sdk import Cerebras
from groq import Groq
import google.generativeai as genai

from config import CEREBRAS_API_KEY, GROQ_API_KEY, GEMINI_API_KEY, CEREBRAS_MODEL, MIN_CONFIDENCE
from verifier import verify_findings, deduplicate_findings


cerebras_client = Cerebras(api_key=CEREBRAS_API_KEY)
groq_client     = Groq(api_key=GROQ_API_KEY)
genai.configure(api_key=GEMINI_API_KEY)
gemini_client   = genai.GenerativeModel("gemini-2.0-flash")


SYSTEM_PROMPT = """You are a senior software engineer doing a careful code review.
Your job is to find real, reproducible bugs and security issues only.

You must respond ONLY with a valid JSON object — no explanation, no markdown, no backticks.

{
  "findings": [
    {
      "type": "bug" | "security",
      "severity": "critical" | "high" | "medium" | "low",
      "confidence": <float between 0.0 and 1.0>,
      "line_reference": "<exact function name or variable name where the issue is>",
      "title": "<short one-line title>",
      "description": "<what is wrong, what input triggers it, what is the observable failure>",
      "fix": "<concrete fix with example code if possible>"
    }
  ]
}

STRICT RULES — read every one carefully:
- Only report "bug" or "security" type findings. Never report performance or suggestions.
- Only report confidence >= 0.92. If you are not certain, return { "findings": [] }.
- line_reference MUST be an exact function name, method name, or variable name that exists in the code. Never write "line 42" or vague descriptions.
- description MUST quote the exact problematic line of code using backticks. If you cannot quote the exact line, do not report the finding.
- NEVER flag stdin size limits, sync fs calls, or event loop blocking in short-lived CLI scripts or one-shot processes.
- NEVER flag environment variables as security issues if they are local config on the user's own machine.
- NEVER flag missing error handling, missing radix in parseInt, or style/best-practice issues.
- NEVER report a finding based on truncated code. If the file appears cut off, ignore anything near the truncation point.
- Before reporting a bug, ask: does this cause a real, observable failure in normal use? If not, skip it.
- Max 2 findings per file. If the code looks clean or you are unsure, return { "findings": [] }"""


SECOND_PASS_PROMPT = """You are a strict code reviewer verifying a list of potential bugs.
For each finding, decide if it is a REAL bug or a FALSE POSITIVE.

A finding is REAL only if:
- The exact code quoted in the description actually exists in the file
- The bug would cause an observable failure in normal use
- It is not a style issue, best practice, or theoretical concern

You must respond ONLY with a valid JSON object:
{
  "confirmed": [<list of finding titles that are REAL bugs>]
}

If none are real, return { "confirmed": [] }"""


def build_user_prompt(file_path: str, language: str, content: str) -> str:
    return f"""Analyze this {language} file for bugs and security vulnerabilities only.
Quote the exact problematic line in your description using backticks.

File: {file_path}

```{language.lower()}
{content}
```"""


def build_verification_prompt(file_path: str, language: str, content: str, findings: list[dict]) -> str:
    findings_text = "\n\n".join([
        f"Finding {i+1}: {f['title']}\n"
        f"Line reference: {f.get('line_reference', 'N/A')}\n"
        f"Description: {f.get('description', 'N/A')}"
        for i, f in enumerate(findings)
    ])

    return f"""Here is a {language} file and a list of potential bugs found in it.
Verify each finding — is it a real bug or a false positive?

File: {file_path}

```{language.lower()}
{content}
```

Findings to verify:
{findings_text}"""


def call_cerebras(messages: list[dict]) -> str:
    response = cerebras_client.chat.completions.create(
        model=CEREBRAS_MODEL,
        messages=messages,
        max_tokens=3000,
        temperature=0.1,
    )
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("Cerebras returned empty response")
    return content.strip()


def call_groq(messages: list[dict]) -> str:
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        max_tokens=3000,
        temperature=0.1,
    )
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("Groq returned empty response")
    return content.strip()


def call_gemini(messages: list[dict]) -> str:
    system_text = next((m["content"] for m in messages if m["role"] == "system"), "")
    user_text   = next((m["content"] for m in messages if m["role"] == "user"), "")
    full_prompt = f"{system_text}\n\n{user_text}"
    response    = gemini_client.generate_content(full_prompt)
    if not response.text:
        raise RuntimeError("Gemini returned empty response")
    return response.text.strip()


def call_llm(messages: list[dict]) -> str:
    """Tries Cerebras → Groq → Gemini in order."""

    try:
        result = call_cerebras(messages)
        print("[Analyzer] Provider: Cerebras ✅")
        return result
    except Exception as e:
        print(f"[Analyzer] Cerebras failed → {e}")

    try:
        result = call_groq(messages)
        print("[Analyzer] Provider: Groq ✅ (fallback)")
        return result
    except Exception as e:
        print(f"[Analyzer] Groq failed → {e}")

    try:
        result = call_gemini(messages)
        print("[Analyzer] Provider: Gemini ✅ (last resort)")
        return result
    except Exception as e:
        print(f"[Analyzer] Gemini also failed → {e}")

    raise RuntimeError("All three providers (Cerebras, Groq, Gemini) failed.")


def parse_findings(raw_text: str) -> list[dict]:
    """Strips markdown fences and parses findings JSON."""
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
    raw_text = raw_text.strip()
    parsed   = json.loads(raw_text)
    return parsed.get("findings", [])


def second_pass_verify(file: dict, findings: list[dict]) -> list[dict]:
    """
    Sends the findings back to the LLM for a second verification pass.
    Only keeps findings the LLM confirms as real in both passes.
    """
    if not findings:
        return []

    messages = [
        {"role": "system", "content": SECOND_PASS_PROMPT},
        {"role": "user",   "content": build_verification_prompt(
            file["path"], file["language"], file["content"], findings
        )},
    ]

    try:
        raw_text = call_llm(messages)

        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        raw_text = raw_text.strip()

        parsed    = json.loads(raw_text)
        confirmed = set(t.lower().strip() for t in parsed.get("confirmed", []))

        if not confirmed:
            print(f"[Analyzer] Second pass: all findings rejected for {file['path']}")
            return []

        kept = [f for f in findings if f.get("title", "").lower().strip() in confirmed]
        rejected = len(findings) - len(kept)
        if rejected:
            print(f"[Analyzer] Second pass: {rejected} finding(s) rejected as false positives.")
        return kept

    except (json.JSONDecodeError, Exception) as e:
        print(f"[Analyzer] Second pass failed → {e} — keeping original findings")
        return findings   # If verification fails, keep originals rather than lose everything


def analyze_file(file: dict) -> list[dict]:
    """
    Analyzes a single file with double-pass validation + line reference verification.
    Pass 1: Find bugs
    Pass 2: LLM verifies its own findings
    Pass 3: verify_findings() checks line references actually exist in the code
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
        # ── Pass 1: Initial analysis ─────────────────────────
        raw_text = call_llm(messages)
        findings = parse_findings(raw_text)

        # Filter by confidence
        findings = [f for f in findings if f.get("confidence", 0) >= MIN_CONFIDENCE]

        if not findings:
            print(f"[Analyzer]   → 0 finding(s) above confidence threshold.")
            return []

        # Attach file context
        for f in findings:
            f["file_path"] = path
            f["language"]  = language

        # ── Pass 2: LLM self-verification ────────────────────
        print(f"[Analyzer]   → {len(findings)} finding(s) — running second pass verification...")
        findings = second_pass_verify(file, findings)

        # ── Pass 3: Line reference verification ─────────────
        findings = verify_findings(findings, file)

        print(f"[Analyzer]   → {len(findings)} finding(s) confirmed after all checks.")
        return findings

    except json.JSONDecodeError as e:
        print(f"[Analyzer] ERROR: Could not parse JSON for {path} → {e}")
        return []
    except RuntimeError:
        print(f"[Analyzer] All providers failed for {path} — skipping.")
        return []
    except Exception as e:
        print(f"[Analyzer] ERROR analyzing {path} → {e}")
        return []


def analyze_repo(files: list[dict]) -> list[dict]:
    """
    Analyzes all files in a repo.
    Returns deduplicated, verified findings sorted by severity.
    """
    all_findings = []

    for file in files:
        findings = analyze_file(file)
        all_findings.extend(findings)

    # Deduplicate across files
    all_findings = deduplicate_findings(all_findings)

    # Sort by severity
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    all_findings.sort(key=lambda f: severity_order.get(f.get("severity", "low"), 3))

    print(f"\n[Analyzer] Total verified findings across all files: {len(all_findings)}")
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
