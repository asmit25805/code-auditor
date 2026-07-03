"""
reporter.py — Module 4
Opens ONE GitHub issue per finding (max 3 issues per repo).
Fetches repo's issue template from .github/ISSUE_TEMPLATE/ and formats
the body to match it — preventing auto-close by template-enforcement bots.
"""

import re
import requests
from github import Github, GithubException
from config import GITHUB_TOKEN


gh = Github(GITHUB_TOKEN)

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

SEVERITY_EMOJI = {
    "critical": "🔴",
    "high":     "🟠",
    "medium":   "🟡",
    "low":      "🔵",
}

TYPE_EMOJI = {
    "bug":      "🐛",
    "security": "🔒",
}

MAX_ISSUES_PER_REPO = 3


# ────────────────────────────────────────────────────────────
# Issue template fetching
# ────────────────────────────────────────────────────────────

def fetch_issue_template(owner: str, repo: str) -> str | None:
    """
    Fetches the repo's bug report issue template from .github/ISSUE_TEMPLATE/.
    Returns the raw template markdown, or None if not found.
    Tries common template filenames in order.
    """
    template_paths = [
        ".github/ISSUE_TEMPLATE/bug_report.md",
        ".github/ISSUE_TEMPLATE/bug-report.md",
        ".github/ISSUE_TEMPLATE/bug.md",
        ".github/ISSUE_TEMPLATE/issue.md",
        ".github/ISSUE_TEMPLATE.md",
        ".github/bug_report.md",
    ]

    for path in template_paths:
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            if resp.status_code == 200:
                import base64
                data    = resp.json()
                content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
                print(f"[Reporter] Found issue template: {path}")
                return content
        except Exception:
            continue

    # Also try listing the ISSUE_TEMPLATE directory
    try:
        url  = f"https://api.github.com/repos/{owner}/{repo}/contents/.github/ISSUE_TEMPLATE"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            files = resp.json()
            # Pick first .md file that looks like a bug report
            for f in files:
                name = f.get("name", "").lower()
                if "bug" in name or "issue" in name or "report" in name:
                    file_url = f.get("download_url")
                    if file_url:
                        r = requests.get(file_url, timeout=10)
                        if r.status_code == 200:
                            print(f"[Reporter] Found issue template: {f['name']}")
                            return r.text
    except Exception:
        pass

    return None


def fill_template(template: str, finding: dict) -> str:
    """
    Fills a GitHub issue template with finding data.
    Replaces common template placeholders and section bodies.
    """
    sev       = finding.get("severity", "medium")
    ftype     = finding.get("type", "bug")
    s_emoji   = SEVERITY_EMOJI.get(sev, "⚪")
    desc      = finding.get("description", "No description provided.")
    fix       = finding.get("fix", "No fix provided.")
    file_path = finding.get("file_path", "Unknown")
    line_ref  = finding.get("line_reference", "N/A")
    confidence = int(finding.get("confidence", 0) * 100)

    # Strip YAML front matter (--- ... ---)
    filled = re.sub(r'^---.*?---\s*', '', template, flags=re.DOTALL)

    # Replace HTML comments (<!-- ... -->) which are instructions to the reporter
    # with our actual content based on what the comment describes
    def replace_comment(match):
        comment = match.group(0).lower()
        if any(w in comment for w in ["describe", "summary", "what", "bug", "problem", "issue"]):
            return desc
        if any(w in comment for w in ["reproduce", "steps", "how to"]):
            return (
                f"1. Use the function/code at `{line_ref}` in `{file_path}`\n"
                f"2. Trigger the code path described above\n"
                f"3. Observe the issue: {desc[:100]}..."
            )
        if any(w in comment for w in ["expected"]):
            return "The code should handle this case safely without the described issue."
        if any(w in comment for w in ["actual", "instead", "happening"]):
            return desc
        if any(w in comment for w in ["fix", "suggest", "solution", "workaround"]):
            return fix
        if any(w in comment for w in ["version", "environment", "os", "platform"]):
            return "N/A — automated static analysis finding"
        return ""

    filled = re.sub(r'<!--.*?-->', replace_comment, filled, flags=re.DOTALL)

    # Fill common markdown checkboxes / dropdowns
    # Severity checkboxes: check the right one
    for level in ["critical", "high", "medium", "low"]:
        if level == sev:
            filled = filled.replace(f"[ ] {level.capitalize()}", f"[x] {level.capitalize()}")
            filled = filled.replace(f"[ ] {level}", f"[x] {level}")
        else:
            # Leave unchecked ones as-is
            pass

    # If template has empty sections we couldn't fill, add a footer
    filled = filled.strip()
    filled += f"""

---

**File:** `{file_path}`
**Location:** `{line_ref}`
**Severity:** {s_emoji} {sev.capitalize()}
**Type:** {ftype.capitalize()}
**Confidence:** {confidence}%

<details>
<summary>About this report</summary>

This finding was generated by an automated audit tool using Llama 3.3 70B.
It passed LLM self-verification and line reference verification before being reported.
Please verify before acting on it.

</details>"""

    return filled


def format_default_body(finding: dict, repo_name: str) -> str:
    """Default issue body when no template is found."""
    sev       = finding.get("severity", "medium")
    ftype     = finding.get("type", "bug")
    s_emoji   = SEVERITY_EMOJI.get(sev, "⚪")
    t_emoji   = TYPE_EMOJI.get(ftype, "🔍")

    return f"""{t_emoji} **{ftype.capitalize()}** · {s_emoji} {sev.capitalize()} · Confidence: {int(finding.get('confidence', 0) * 100)}%

**File:** `{finding.get('file_path', 'Unknown')}`
**Location:** `{finding.get('line_reference', 'N/A')}`

---

### What's wrong

{finding.get('description', 'No description provided.')}

### Suggested fix

{finding.get('fix', 'No fix provided.')}

---

### Steps to reproduce

1. Look at `{finding.get('line_reference', 'N/A')}` in `{finding.get('file_path', 'Unknown')}`
2. Trigger the code path described above
3. Observe the issue

### Expected behavior

The code should handle this case safely without the described issue.

### Actual behavior

{finding.get('description', 'No description provided.')}

---

<details>
<summary>About this report</summary>

This finding was generated by an automated audit tool using Llama 3.3 70B.
It passed LLM self-verification and line reference verification before being reported.
Please verify before acting on it.

</details>"""


# ────────────────────────────────────────────────────────────
# Main issue opener
# ────────────────────────────────────────────────────────────

def open_issues(repo_full_name: str, findings: list[dict]) -> list[str]:
    """
    Opens one GitHub issue per finding, up to MAX_ISSUES_PER_REPO.
    Fetches and follows the repo's issue template if one exists.
    Only opens issues for medium+ severity findings.
    Returns list of issue URLs opened.
    """
    if not findings:
        print(f"[Reporter] No findings for {repo_full_name} — skipping.")
        return []

    significant = [
        f for f in findings
        if f.get("severity") in ("critical", "high", "medium")
    ]

    if not significant:
        print(f"[Reporter] Only low-severity findings for {repo_full_name} — skipping.")
        return []

    to_report = significant[:MAX_ISSUES_PER_REPO]

    print(f"[Reporter] Opening {len(to_report)} issue(s) on {repo_full_name} "
          f"(capped from {len(significant)} significant findings)...")

    try:
        repo = gh.get_repo(repo_full_name)
    except GithubException as e:
        print(f"[Reporter] Could not access repo {repo_full_name} → {e}")
        return []

    # Fetch issue template once for the whole repo
    owner, repo_name = repo_full_name.split("/", 1)
    template = fetch_issue_template(owner, repo_name)
    if not template:
        print(f"[Reporter] No issue template found — using default format.")

    issue_urls = []

    for finding in to_report:
        ftype = finding.get("type", "bug")
        title = f"{TYPE_EMOJI.get(ftype, '🔍')} {finding.get('title', 'Potential issue found')}"

        if template:
            body = fill_template(template, finding)
        else:
            body = format_default_body(finding, repo_full_name)

        try:
            issue = repo.create_issue(title=title, body=body)
            print(f"[Reporter] ✅ Issue opened → {issue.html_url}")
            issue_urls.append(issue.html_url)

        except GithubException as e:
            if e.status == 410:
                print(f"[Reporter] Issues disabled on {repo_full_name} — stopping.")
                break
            elif e.status == 403:
                print(f"[Reporter] No permission to open issues on {repo_full_name} — stopping.")
                break
            else:
                print(f"[Reporter] GitHub error → {e.status}: {e.data}")
        except Exception as e:
            print(f"[Reporter] Unexpected error → {e}")

    return issue_urls


# ── Quick test ───────────────────────────────────────────────
if __name__ == "__main__":
    sample = {
        "type":           "security",
        "severity":       "medium",
        "confidence":     0.95,
        "line_reference": "get_user",
        "title":          "SQL injection via f-string in get_user()",
        "description":    "User input is directly interpolated into an SQL query: `query = f\"SELECT * FROM users WHERE username = '{username}'\"`. An attacker can manipulate the query.",
        "fix":            "Use parameterized queries: `cursor.execute('SELECT * FROM users WHERE username = ?', (username,))`",
        "file_path":      "src/db.py",
        "language":       "Python",
    }
    body = format_default_body(sample, "example/repo")
    print(body)
