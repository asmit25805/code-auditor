"""
main.py — Entry Point
Orchestrates the full pipeline:
Fetch trending repos → Pull code → Analyze → Report → Log
"""

import sys
from pathlib import Path

# Make sure src/ is importable
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.fetcher     import fetch_trending_repos
from src.code_puller import pull_code_files
from src.analyzer    import analyze_repo
from src.reporter    import open_issue
from src.database    import init_db, get_already_scanned, mark_repo_scanned, print_stats


def run_audit():
    print("=" * 55)
    print("  🤖 CODE AUDITOR — Starting Run")
    print("=" * 55)

    # Step 1: Initialize database
    init_db()

    # Step 2: Get repos we've already seen so we don't duplicate
    already_seen = get_already_scanned()
    print(f"\n[Main] {len(already_seen)} repo(s) already scanned — will skip these.\n")

    # Step 3: Fetch trending repos
    repos = fetch_trending_repos(already_seen)

    if not repos:
        print("[Main] No new repos to audit today. Done.")
        print_stats()
        return

    # Step 4: Process each repo
    for repo in repos:
        full_name = repo["full_name"]
        print(f"\n{'─' * 55}")
        print(f"  📦 Auditing: {full_name}  (★{repo['stars']:,})")
        print(f"{'─' * 55}")

        # Pull code files from the repo
        files = pull_code_files(repo)

        if not files:
            print(f"[Main] No analyzable files found in {full_name}. Skipping.")
            mark_repo_scanned(full_name, repo["stars"], [], None)
            continue

        # Analyze all files with Cerebras
        findings = analyze_repo(files)

        # Open a GitHub issue if findings are significant
        issue_url = open_issue(full_name, findings)

        # Log everything to our database
        mark_repo_scanned(full_name, repo["stars"], findings, issue_url)

    # Step 5: Print final stats
    print(f"\n{'=' * 55}")
    print("  ✅ Audit Run Complete")
    print(f"{'=' * 55}")
    print_stats()


if __name__ == "__main__":
    run_audit()
