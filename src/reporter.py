"""
reporter.py — Module 4
Formats findings into clean markdown and opens a GitHub issue.
Only opens an issue if there are actual findings worth reporting.
"""

from github import Github, GithubException
from config import GITHUB_TOKEN


gh = Github(GITHUB_TOKEN)

SEVERITY_EMOJI = {
    "critical": "🔴",
    "high":     "🟠",
    "medium":   "🟡",
    "low":      "🔵",
}

TYPE_EMOJI = {
    "bug":         "🐛",
    "security":    "🔒",
    "performance": "⚡",
    "suggestion":  "💡",
}

ISSUE_LABEL_MAP = {
    "critical": "bug",
    "high":     "bug",
    "medium":   "enhancement",
    "low":      "enhancement",
}


def format_finding(finding: dict, index: int) -> str:
    """Formats a single finding into a readable markdown block."""
    sev   = finding.get("severity", "medium")
    ftype = finding.get("type", "bug")
    s_emoji = SEVERITY_EMOJI.get(sev, "⚪")
    t_emoji = TYPE_EMOJI.get(ftype, "🔍")

    return f"""### {index}. {t_emoji} {finding.get('title', 'Unnamed Issue')}

| Field | Details |
|---|---|
| **Severity** | {s_emoji} {sev.capitalize()} |
| **Type** | {ftype.capitalize()} |
| **File** | `{finding.get('file_path', 'Unknown')}` |
| **Location** | {finding.get('line_reference', 'N/A')} |
| **Confidence** | {int(finding.get('confidence', 0) * 100)}% |

**Problem:**
{finding.get('description', 'No description provided.')}

**Suggested Fix:**
{finding.get('fix', 'No fix provided.')}

---"""


def format_issue_body(findings: list[dict], repo_name: str) -> str:
    """Builds the full issue body from all findings."""
    finding_blocks = "\n\n".join(
        format_finding(f, i + 1) for i, f in enumerate(findings)
    )

    severity_counts = {}
    for f in findings:
        sev = f.get("severity", "medium")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    summary_parts = [
        f"{SEVERITY_EMOJI.get(sev, '⚪')} {count} {sev}"
        for sev, count in severity_counts.items()
    ]
    summary_line = " · ".join(summary_parts)

    return f"""##  Code Audit Report

> All findings are reviewed for confidence before posting.
> Please verify each finding before acting on it.

**Repository:** `{repo_name}`
**Findings:** {len(findings)} issue(s) found — {summary_line}

---

{finding_blocks}

<details>
<summary>About this report</summary>

This report was generated using Llama 3.3 70B via the Cerebras API.
Only findings with ≥80% confidence are included.
False positives are possible — use your own judgment.

</details>"""


def open_issue(repo_full_name: str, findings: list[dict]) -> str | None:
    """
    Opens a GitHub issue on the given repo with all findings.
    Returns the issue URL if successful, None otherwise.

    repo_full_name: e.g. "torvalds/linux"
    """
    if not findings:
        print(f"[Reporter] No findings for {repo_full_name} — skipping issue.")
        return None

    # Only open an issue if there's at least one medium+ severity finding
    significant = [f for f in findings if f.get("severity") in ("critical", "high", "medium")]
    if not significant:
        print(f"[Reporter] Only low-severity findings for {repo_full_name} — skipping issue.")
        return None

    title  = f"🤖 Code Audit: {len(findings)} potential issue(s) found"
    body   = format_issue_body(findings, repo_full_name)

    print(f"[Reporter] Opening issue on {repo_full_name}...")

    try:
        repo  = gh.get_repo(repo_full_name)
        issue = repo.create_issue(title=title, body=body)
        print(f"[Reporter] ✅ Issue opened → {issue.html_url}")
        return issue.html_url

    except GithubException as e:
        # Issues may be disabled on the repo
        if e.status == 410:
            print(f"[Reporter] Issues are disabled on {repo_full_name} — skipping.")
        elif e.status == 403:
            print(f"[Reporter] No permission to open issues on {repo_full_name} — skipping.")
        else:
            print(f"[Reporter] GitHub error on {repo_full_name} → {e.status}: {e.data}")
        return None
    except Exception as e:
        print(f"[Reporter] Unexpected error → {e}")
        return None


# ── Quick test (prints formatted issue, doesn't actually post) ──
if __name__ == "__main__":
    sample_findings = [
        {
            "type":           "security",
            "severity":       "critical",
            "confidence":     0.97,
            "line_reference": "get_user() function",
            "title":          "SQL Injection vulnerability via string formatting",
            "description":    "User input is directly interpolated into an SQL query using an f-string. This allows an attacker to manipulate the query structure.",
            "fix":            "Use parameterized queries: cursor.execute('SELECT * FROM users WHERE username = ?', (username,))",
            "file_path":      "src/db.py",
            "language":       "Python",
        },
        {
            "type":           "security",
            "severity":       "high",
            "confidence":     0.95,
            "line_reference": "read_config() function",
            "title":          "Hardcoded credentials in source code",
            "description":    "Secret keys and passwords are stored as plaintext string literals in the source code, exposing them to anyone with repo access.",
            "fix":            "Move secrets to environment variables and load them with os.getenv(). Never commit credentials to version control.",
            "file_path":      "src/config.py",
            "language":       "Python",
        },
    ]

    body = format_issue_body(sample_findings, "example/repo")
    print(body)
