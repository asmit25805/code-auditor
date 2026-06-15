import os
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ────────────────────────────────────────────────
GITHUB_TOKEN     = os.getenv("GITHUB_TOKEN")
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY")
GROQ_API_KEY     = os.getenv("GROQ_API_KEY")

# ── Trending Repo Settings ──────────────────────────────────
TRENDING_DAYS        = 14          # Look at repos created in last N days
TRENDING_MIN_STARS   = 80         # Ignore repos with fewer stars than this
REPOS_PER_RUN        = 5          # How many repos to audit per run

# ── Code Fetching Settings ──────────────────────────────────
MAX_FILE_SIZE_KB     = 100        # Skip files larger than this (too big for LLM)
MAX_FILES_PER_REPO   = 20          # Max files to analyze per repo
MAX_CHARS_PER_FILE   = 10000       # Truncate files beyond this character limit

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
CEREBRAS_MODEL = "llama3.1-70b"
MIN_CONFIDENCE       = 0.80       # Only report findings above this confidence

# ── Files/Folders to always skip ────────────────────────────
SKIP_PATHS = [
    "test", "tests", "__pycache__", "node_modules",
    "vendor", "dist", "build", ".git", "migrations",
    "fixtures", "mock", "mocks", "spec", "specs"
]
