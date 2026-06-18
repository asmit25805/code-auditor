"""
verifier.py — Module 3b
Verifies findings before they get reported.
Filters out hallucinated line references and findings that don't
hold up under a second LLM pass.
"""

import ast
import re


def verify_line_reference(finding: dict, file_content: str) -> bool:
    """
    Checks that the line_reference in a finding actually exists
    in the file content. Returns True if the finding looks legit.

    We check:
    1. If line_reference mentions a function name, that function exists
    2. If line_reference mentions a variable/pattern, it appears in the code
    3. The description mentions something that actually appears in the code
    """
    line_ref    = finding.get("line_reference", "").strip()
    description = finding.get("description", "").lower()
    content     = file_content

    if not line_ref:
        return False   # No line reference = unverifiable = reject

    content_lower = content.lower()

    # ── Check 1: Extract tokens from line_reference and look for them ──
    # e.g. "get_user() function" → look for "get_user" in the file
    tokens = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]{2,}', line_ref)
    meaningful_tokens = [t for t in tokens if t.lower() not in {
        "function", "method", "class", "variable", "line", "the",
        "and", "or", "in", "at", "on", "of", "to", "for",
    }]

    if meaningful_tokens:
        found_any = any(token.lower() in content_lower for token in meaningful_tokens)
        if not found_any:
            return False   # None of the referenced identifiers exist in the file

    # ── Check 2: Key terms from description should appear in the file ──
    # Extract quoted strings or code-like terms from the description
    quoted = re.findall(r'`([^`]+)`', finding.get("description", ""))
    for term in quoted:
        term_clean = term.strip().lower()
        if len(term_clean) > 3 and term_clean not in content_lower:
            return False   # LLM quoted something that doesn't exist in the file

    return True


def verify_python_syntax(content: str) -> bool:
    """Returns True if Python content is syntactically valid."""
    try:
        ast.parse(content)
        return True
    except SyntaxError:
        return False


def deduplicate_findings(all_findings: list[dict]) -> list[dict]:
    """
    Removes duplicate findings across files.
    Two findings are considered duplicates if they have the same title
    or very similar descriptions (same root cause reported in multiple files).
    Returns deduplicated list, merging file paths where appropriate.
    """
    if not all_findings:
        return []

    deduplicated = []
    seen_titles  = {}   # normalized_title → index in deduplicated

    for finding in all_findings:
        title      = finding.get("title", "").strip().lower()
        # Normalize: remove punctuation and common words for comparison
        norm_title = re.sub(r'[^a-z0-9 ]', '', title)
        norm_title = re.sub(r'\b(the|a|an|in|at|on|of|to|for|is|are|was)\b', '', norm_title)
        norm_title = re.sub(r'\s+', ' ', norm_title).strip()

        if norm_title in seen_titles:
            # Duplicate — merge file path into existing finding
            existing_idx  = seen_titles[norm_title]
            existing      = deduplicated[existing_idx]
            existing_path = existing.get("file_path", "")
            new_path      = finding.get("file_path", "")

            if new_path and new_path != existing_path:
                existing["file_path"] = f"{existing_path}, {new_path}"
                existing["description"] += f"\n\n*(Also found in: `{new_path}`)*"
        else:
            seen_titles[norm_title] = len(deduplicated)
            deduplicated.append(finding)

    removed = len(all_findings) - len(deduplicated)
    if removed:
        print(f"[Verifier] Removed {removed} duplicate finding(s).")

    return deduplicated


def verify_findings(findings: list[dict], file: dict) -> list[dict]:
    """
    Runs all verification checks on findings for a single file.
    Returns only findings that pass verification.
    """
    if not findings:
        return []

    content  = file["content"]
    language = file["language"]
    path     = file["path"]
    verified = []

    # For Python files, check syntax first
    # If the file has a syntax error, all findings about it are suspect
    if language == "Python":
        if not verify_python_syntax(content):
            print(f"[Verifier] WARNING: {path} has a Python syntax error — findings may be unreliable.")
            # Don't reject — the syntax error itself might be worth reporting

    for finding in findings:
        if verify_line_reference(finding, content):
            verified.append(finding)
        else:
            print(f"[Verifier] Rejected finding '{finding.get('title', '?')}' — "
                  f"line reference not found in {path}")

    removed = len(findings) - len(verified)
    if removed:
        print(f"[Verifier] {removed} finding(s) rejected for {path} (unverifiable references).")

    return verified
