"""
main.py — Entry Point
Orchestrates the full pipeline:
Fetch repos → Pull code + README → Classify → Analyze → Report → Log
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.fetcher     import fetch_trending_repos
from src.code_puller import pull_code_files
from src.analyzer    import analyze_repo, classify_repo
from src.reporter    import open_issues
from src.database    import init_db, get_already_scanned, mark_repo_scanned, print_stats


def run_audit():
    print("=" * 55)
    print("  🤖 CODE AUDITOR — Starting Run")
    print("=" * 55)

    init_db()

    already_seen = get_already_scanned()
    print(f"\n[Main] {len(already_seen)} repo(s) already scanned — will skip these.\n")

    repos = fetch_trending_repos(already_seen)

    if not repos:
        print("[Main] No new repos to audit today. Done.")
        print_stats()
        return

    for repo in repos:
        full_name = repo["full_name"]
        print(f"\n{'─' * 55}")
        print(f"  📦 Auditing: {full_name}  (★{repo['stars']:,})")
        print(f"{'─' * 55}")

        # Pull code files + README
        files, readme, file_tree = pull_code_files(repo)

        if not files:
            print(f"[Main] No analyzable files found in {full_name}. Marking as scanned to skip in future.")
            mark_repo_scanned(full_name, repo["stars"], [], None)
            continue

        # Classify repo using Gemini + README
        print(f"\n[Main] Classifying repo type...")
        repo_context = classify_repo(readme, file_tree)

        # Analyze files with full pipeline
        findings = analyze_repo(files, repo_context)

        # Open one issue per finding (max 3)
        issue_urls = open_issues(full_name, findings)

        # Log to DB
        mark_repo_scanned(
            full_name,
            repo["stars"],
            findings,
            issue_urls[0] if issue_urls else None,
        )

    print(f"\n{'=' * 55}")
    print("  ✅ Audit Run Complete")
    print(f"{'=' * 55}")
    print_stats()


if __name__ == "__main__":
    run_audit()
