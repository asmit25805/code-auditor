"""
fetcher.py — Module 1
Fetches trending GitHub repositories using the GitHub Search API.
No scraping. Uses the official API with your token.
"""

import requests
from datetime import datetime, timedelta, timezone
from config import GITHUB_TOKEN, TRENDING_DAYS, TRENDING_MIN_STARS, REPOS_PER_RUN


HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def get_date_cutoff() -> str:
    """Returns a date string N days ago in GitHub's query format."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=TRENDING_DAYS)
    return cutoff.strftime("%Y-%m-%d")


def fetch_trending_repos(already_seen: set[str]) -> list[dict]:
    """
    Fetches trending repos from GitHub created in the last N days,
    sorted by stars. Skips any repos already in the seen set.

    Returns a list of repo dicts with the fields we care about.
    """
    cutoff_date = get_date_cutoff()

    url = "https://api.github.com/search/repositories"
    params = {
        "q":        f"created:>{cutoff_date} stars:>{TRENDING_MIN_STARS}",
        "sort":     "stars",
        "order":    "desc",
        "per_page": 30,   # Fetch more than we need so we have options after filtering
    }

    print(f"[Fetcher] Searching repos created after {cutoff_date} with {TRENDING_MIN_STARS}+ stars...")

    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"[Fetcher] ERROR: GitHub API request failed → {e}")
        return []

    data = response.json()
    all_repos = data.get("items", [])
    print(f"[Fetcher] Found {len(all_repos)} repos. Filtering...")

    results = []
    for repo in all_repos:
        full_name = repo["full_name"]  # e.g. "torvalds/linux"

        # Skip if we've already audited this repo
        if full_name in already_seen:
            print(f"[Fetcher] Skipping {full_name} — already audited.")
            continue

        # Skip forks (they're someone else's code, not original)
        if repo.get("fork"):
            continue

        # Skip archived repos
        if repo.get("archived"):
            continue

        results.append({
            "full_name":   full_name,
            "name":        repo["name"],
            "owner":       repo["owner"]["login"],
            "description": repo.get("description", "No description"),
            "stars":       repo["stargazers_count"],
            "language":    repo.get("language", "Unknown"),
            "url":         repo["html_url"],
            "default_branch": repo.get("default_branch", "main"),
        })

        if len(results) >= REPOS_PER_RUN:
            break

    print(f"[Fetcher] Selected {len(results)} repos to audit.")
    return results


# ── Quick test ───────────────────────────────────────────────
if __name__ == "__main__":
    repos = fetch_trending_repos(already_seen=set())
    if not repos:
        print("No repos found. Check your GITHUB_TOKEN in .env")
    else:
        print("\n── Trending Repos ──────────────────────────")
        for r in repos:
            print(f"  ★ {r['stars']:,}  {r['full_name']}  [{r['language']}]")
            print(f"     {r['description'][:80]}")
            print()
