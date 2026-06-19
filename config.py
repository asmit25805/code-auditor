import os
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ────────────────────────────────────────────────
GITHUB_TOKEN     = os.getenv("GITHUB_TOKEN")
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY")
GROQ_API_KEY     = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY   = os.getenv("GEMINI_API_KEY")

# ── Trending Repo Settings ──────────────────────────────────
TRENDING_DAYS        = 45          # Look at repos created in last N days
TRENDING_MIN_STARS   = 300         # Ignore repos with fewer stars than this
REPOS_PER_RUN        = 5           # How many repos to audit per run

# ── Code Fetching Settings ──────────────────────────────────
MAX_FILE_SIZE_KB     = 150         # Skip files larger than this (too big for LLM)
MAX_FILES_PER_REPO   = 35          # Max files to analyze per repo
MAX_CHARS_PER_FILE   = 15000       # Truncate files beyond this character limit

# ── Supported file extensions → language name ───────────────
SUPPORTED_EXTENSIONS = {
    ".py":   "Python",
    ".js":   "JavaScript",
    ".ts":   "TypeScript",
    ".java": "Java",
    ".go":   "Go",
    ".rs":   "Rust",
    ".c":    "C",
    ".cpp":  "C++",
    ".rb":   "Ruby",
    ".php":  "PHP",
}

# ── AI Settings ─────────────────────────────────────────────
CEREBRAS_MODEL   = "gpt-oss-120b"
MIN_CONFIDENCE   = 0.92

# ── Files/Folders to always skip ────────────────────────────
SKIP_PATHS = [
    # Dependencies / build output
    "node_modules", "vendor", "dist", "build", ".git",
    "__pycache__",
    # Tests
    "test", "tests", "spec", "specs", "__tests__",
    # Migrations / fixtures
    "migrations", "fixtures", "mock", "mocks",
    # Examples / docs
    "example", "examples", "demo", "demos",
    "docs", "doc", "documentation",
    # Benchmarks / scripts
    "benchmark", "benchmarks", "hack", "hacks",
    "scripts",        # usually one-off maintenance scripts, not production code
    # Config/build files by name pattern
    "tsdown.config", "vite.config", "webpack.config",
    "rollup.config",  "babel.config",  "jest.config",
    "eslint.config",  "prettier.config", "tailwind.config",
    "postcss.config", "next.config",   "nuxt.config",
    "svelte.config",  "astro.config",  "vitest.config",
    ".vitepress",
]
