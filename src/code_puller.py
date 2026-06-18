"""
code_puller.py — Module 2
Given a repo, fetches the actual source code files we want to analyze.
Respects file size limits and skips test/vendor/build folders.
For large repos, scores files by importance and picks the best ones.
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

# Folders that strongly suggest real application logic
HIGH_VALUE_DIRS = {
    "src", "lib", "core", "api", "server", "backend",
    "app", "pkg", "internal", "cmd", "handler", "handlers",
    "service", "services", "controller", "controllers",
    "middleware", "router", "routes", "auth", "db", "database",
}

# Filenames (without extension) that suggest security/logic-heavy code
HIGH_VALUE_NAMES = {
    "auth", "authentication", "authorization", "login", "session",
    "token", "jwt", "oauth", "password", "crypto", "encrypt",
    "db", "database", "query", "store", "storage", "cache",
    "router", "routes", "handler", "server", "api",
    "payment", "billing", "webhook", "middleware", "security",
    "upload", "file", "permission", "rbac", "config",
}

# Config/build filenames to deprioritize even if not in SKIP_PATHS
LOW_VALUE_NAMES = {
    "vite.config", "tsdown.config", "webpack.config", "rollup.config",
    "babel.config", "jest.config", "eslint.config", "prettier.config",
    "tailwind.config", "postcss.config", "next.config", "nuxt.config",
    "svelte.config", "astro.config", "vitest.config", "tsconfig",
    "__init__", "index",   # index/init files rarely have bugs
}


def score_file(path: str, size_bytes: int) -> int:
    """
    Returns an importance score for a file.
    Higher = more worth analyzing.
    Called before fetching content so we only use path + size.
    """
    score = 0
    parts      = path.lower().replace("\\", "/").split("/")
    filename   = parts[-1]
    name_no_ext = filename.rsplit(".", 1)[0] if "." in filename else filename

    # ── Directory bonuses ────────────────────────────────────
    for part in parts[:-1]:   # all dir components
        if part in HIGH_VALUE_DIRS:
            score += 30
            break   # only count once

    # Penalize files sitting at root level (often config)
    depth = len(parts) - 1
    if depth == 0:
        score -= 20
    elif depth == 1:
        score += 5

    # ── Filename bonuses/penalties ───────────────────────────
    if name_no_ext in HIGH_VALUE_NAMES:
        score += 40
    if name_no_ext in LOW_VALUE_NAMES:
        score -= 50

    # Partial match on high value names (e.g. "user_auth.py")
    for hvn in HIGH_VALUE_NAMES:
        if hvn in name_no_ext and name_no_ext not in HIGH_VALUE_NAMES:
            score += 15
            break

    # ── Size bonus — bigger files have more code to audit ────
    size_kb = size_bytes / 1024
    if size_kb > 5:
        score += 10
    if size_kb > 15:
        score += 10
    if size_kb > 30:
        score += 5
    # But very large files are truncated anyway, diminishing returns
    if size_kb > MAX_FILE_SIZE_KB * 0.8:
        score -= 10

    return score


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

        size_kb = data.get("size", 0) / 1024
        if size_kb > MAX_FILE_SIZE_KB:
            print(f"[Puller] Skipping {file_path} — too large ({size_kb:.1f} KB)")
            return None

        encoded = data.get("content", "")
        decoded = base64.b64decode(encoded).decode("utf-8", errors="replace")

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
    For large repos, scores all candidates and picks the most important ones.

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
        if item.get("type") != "blob":
            continue

        path = item["path"]
        ext  = get_file_extension(path)

        if ext not in SUPPORTED_EXTENSIONS:
            continue

        if should_skip_path(path):
            continue

        size_bytes = item.get("size", 0)

        candidate_files.append({
            "path":     path,
            "language": SUPPORTED_EXTENSIONS[ext],
            "score":    score_file(path, size_bytes),
            "size":     size_bytes,
        })

    total_candidates = len(candidate_files)

    # Sort by score descending — best files first
    candidate_files.sort(key=lambda f: f["score"], reverse=True)

    if total_candidates > MAX_FILES_PER_REPO:
        print(f"[Puller] {total_candidates} eligible files — scoring and picking top {MAX_FILES_PER_REPO}.")
    else:
        print(f"[Puller] Found {total_candidates} eligible source files.")

    fetched = []
    for file_info in candidate_files[:MAX_FILES_PER_REPO]:
        score_str = f" (score: {file_info['score']})" if total_candidates > MAX_FILES_PER_REPO else ""
        print(f"[Puller]   → {file_info['path']}{score_str}")
        content = fetch_file_content(owner, name, file_info["path"])

        if content and len(content.strip()) > 50:
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
