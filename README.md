# Code Auditor

An automated security and bug-finding pipeline that scans public GitHub repositories, verifies findings through a multi-pass LLM review, and opens issues directly on the target repo — with no human in the loop.

Built solo. Runs on free-tier inference. No funding, no team.

---

## What it does

Code Auditor scans a codebase, generates candidate findings with an LLM, then runs those findings back through a second and third pass before anything gets posted as a GitHub issue. The goal isn't volume — it's making sure a maintainer can trust the report enough to act on it without doing the verification themselves.

**Pipeline:**

1. **Scan** — pulls a target repo, walks the source tree
2. **First-pass analysis** — LLM flags candidate bugs/vulnerabilities, must quote the exact line of code
3. **Second-pass verification** — an independent LLM pass asks "is this actually real, or a false positive?"
4. **Static verification layer** — code checks that every function/variable/file path referenced in a finding actually exists — hallucinated references get rejected automatically
5. **Confidence gate** — only findings above a 0.92 confidence threshold survive
6. **Context check** — the pipeline reads the project type before flagging anything context-dependent (e.g. "unbounded stdin" is a real issue in a web server, a non-issue in a CLI tool)
7. **Template-aware reporting** — before posting, the bot reads the repo's `CONTRIBUTING.md` (if one exists) and conforms the report to the repo's own bug-report format and conventions, instead of posting a generic template
8. **Post** — opens a GitHub issue with the finding, the exact line reference, and severity

12 verification layers total sit between "LLM had a thought" and "issue gets posted."

---

## Why the template-aware step exists

Early versions of this bot ignored repo conventions entirely and posted a fixed format regardless of what the maintainer expected. At least one maintainer rejected a report specifically because it didn't match their contribution guidelines. The fix: read `CONTRIBUTING.md` before generating the report and adapt to it, rather than assuming a one-size-fits-all format works everywhere.

---

## Two report formats, two very different track records

This project went through a real format shift, and it's worth being honest about both sides of it rather than only showing the good numbers.

**Early / batch format** — one issue containing many findings at once (10-30+ per report). This is where the false-positive problem lived. Maintainers across several repos flagged these as alert fatigue, asked for findings to be split up, or closed them with a one-word "tldr." This format is retired.

**Current / scoped format** — one finding per issue, verified end-to-end through the full pipeline above. Across the most recent batch of scoped reports, this format has produced real, maintainer-confirmed fixes with a single confirmed false positive in the set — roughly a 5% false-positive rate, a large improvement over the batch era.

The lesson: verification layers matter less than report granularity. A confident LLM producing 25 findings in one issue will always read as spam, no matter how good the underlying analysis is. One well-scoped, well-verified finding per issue is what actually gets read and fixed.

---

## Results

Confirmed real bugs fixed by maintainers include (non-exhaustive):

- **deeplethe/forkd** — blocking `accept()` deadlock, merged same day
- **nubjs/nub** — path traversal via unvalidated `bin_subpath`, fixed in v0.2.4; cache key bug, fixed in same release
- **Helvesec/rmux** — deserializer bug, resolved in v0.7.1
- **vercel-labs/zerolang** — NULL pointer dereference, confirmed and fixed
- **vercel/eve** — undefined auth secret + null AbortSignal bug, both fixed
- **BigPizzaV3/CodexPlusPlus** — arbitrary file write via unchecked backup path, fixed and pushed to main
- **nexu-io/html-anything** — zero-duration handling bug and unsanitized HTML injection via `document.write`, both confirmed real

20+ verified bugs fixed across public repos overall, spanning both format eras.

---

## Stack

- **Language:** Python
- **Primary inference:** Cerebras (Llama 3.3 70B, 1M free tokens/day)
- **Fallback inference:** Groq
- **Scheduling:** GitHub Actions cron
- **State tracking:** SQLite (tracks what's already been scanned to avoid duplicate reports)
- **Cost:** $0 to run — entirely on free tiers

---

## Honest limitations

- Confidence scoring reduces but does not eliminate false positives
- Context-dependent findings (intentional design choices that look like bugs) are the main remaining failure mode
- The pipeline audits public repos; it does not have write access and never opens PRs on its own — only issues, for a human maintainer to act on
- This is a solo research/tooling project, not a commercial product

---

## License

CC BY-NC on the tool itself. See repo for full license text.

---

Built and maintained by [@asmit25805](https://github.com/asmit25805).
