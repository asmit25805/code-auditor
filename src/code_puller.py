"""
code_puller.py — Module 2
Given a repo, fetches the actual source code files we want to analyze.
Respects file size limits and skips test/vendor/build folders.
"""

import base64
import requests
from config import (
    GITHUB_TOKEN, SUPPORTED_EXTENSIONS,
    MAX_FILE_SIZE_KB, MAX_FILES_PER_REPO,
    MAX_CHARS_PER_FILE, SKIP_PATHS
)


HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def should_skip_path(path: str) -> bool:
    """Returns True if this file path should be skipped."""
    path_lower = path.lower()
    return any(skip in path_lower for skip in SKIP_PATHS)


def get_file_extension(filename: str) -> str:
    """Returns the file extension including the dot, e.g. '.py'"""
    if "." in filename:
        return "." + filename.rsplit(".", 1)[-1].lower()
    return ""


def fetch_repo_tree(owner: str, repo: str, branch: str) -> list[dict]:
    """
    Fetches the full file tree of a repo using GitHub's git trees API.
    recursive=1 means we get all files in all subdirectories at once.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}"
    params = {"recursive": "1"}

    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json().get("tree", [])
    except requests.RequestException as e:
        print(f"[Puller] ERROR fetching tree for {owner}/{repo} → {e}")
        return []


def fetch_file_content(owner: str, repo: str, file_path: str) -> str | None:
    """
    Fetches the decoded content of a single file from GitHub.
    Returns None if the file is too large or can't be fetched.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        # GitHub returns size in bytes
        size_kb = data.get("size", 0) / 1024
        if size_kb > MAX_FILE_SIZE_KB:
            print(f"[Puller] Skipping {file_path} — too large ({size_kb:.1f} KB)")
            return None

        # Content is base64 encoded
        encoded = data.get("content", "")
        decoded = base64.b64decode(encoded).decode("utf-8", errors="replace")

        # Truncate if needed to stay within LLM context limits
        if len(decoded) > MAX_CHARS_PER_FILE:
            decoded = decoded[:MAX_CHARS_PER_FILE] + "\n\n# ... [truncated]"

        return decoded

    except (requests.RequestException, UnicodeDecodeError, Exception) as e:
        print(f"[Puller] ERROR fetching {file_path} → {e}")
        return None


def pull_code_files(repo: dict) -> list[dict]:
    """
    Main function. Given a repo dict (from fetcher.py),
    returns a list of files with their content and language.

    Each item: { path, language, content }
    """
    owner  = repo["owner"]
    name   = repo["name"]
    branch = repo["default_branch"]

    print(f"\n[Puller] Fetching file tree for {owner}/{name}...")
    tree = fetch_repo_tree(owner, name, branch)

    if not tree:
        return []

    # Filter to only source code files we support
    candidate_files = []
    for item in tree:
        if item.get("type") != "blob":   # Only files, not folders
            continue

        path = item["path"]
        ext  = get_file_extension(path)

        if ext not in SUPPORTED_EXTENSIONS:
            continue

        if should_skip_path(path):
            continue

        candidate_files.append({
            "path":     path,
            "language": SUPPORTED_EXTENSIONS[ext],
        })

    print(f"[Puller] Found {len(candidate_files)} eligible source files. Fetching up to {MAX_FILES_PER_REPO}...")

    # Prioritize root-level and src/ files — they're usually the most important
    candidate_files.sort(key=lambda f: (f["path"].count("/"), f["path"]))

    fetched = []
    for file_info in candidate_files[:MAX_FILES_PER_REPO]:
        print(f"[Puller]   → {file_info['path']}")
        content = fetch_file_content(owner, name, file_info["path"])

        if content and len(content.strip()) > 50:  # Skip near-empty files
            fetched.append({
                "path":     file_info["path"],
                "language": file_info["language"],
                "content":  content,
            })

    print(f"[Puller] Successfully fetched {len(fetched)} files.")
    return fetched


# ── Quick test ───────────────────────────────────────────────
if __name__ == "__main__":
    test_repo = {
        "owner":          "pallets",
        "name":           "flask",
        "default_branch": "main",
    }
    files = pull_code_files(test_repo)
    for f in files:
        print(f"\n── {f['path']} [{f['language']}] ──")
        print(f["content"][:200], "...")
