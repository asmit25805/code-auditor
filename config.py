import os
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ────────────────────────────────────────────────
GITHUB_TOKEN     = os.getenv("GITHUB_TOKEN")
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY")
GROQ_API_KEY     = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY   = os.getenv("GEMINI_API_KEY")

# ── Trending Repo Settings ──────────────────────────────────
TRENDING_DAYS        = 250
TRENDING_MIN_STARS   = 800
REPOS_PER_RUN        = 5

# ── Code Fetching Settings ──────────────────────────────────
MAX_FILE_SIZE_KB     = 150
MAX_FILES_PER_REPO   = 25  
MAX_CHARS_PER_FILE   = 15000

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
    "node_modules", "vendor", "dist", "build", ".git", "__pycache__",
    # Tests
    "test", "tests", "spec", "specs", "__tests__",
    # Migrations / fixtures
    "migrations", "fixtures", "mock", "mocks",
    # Examples / docs
    "example", "examples", "demo", "demos", "docs", "doc",
    # Benchmarks / scripts
    "benchmark", "benchmarks", "scripts",
    # Config/build file name patterns
    "tsdown.config", "vite.config", "webpack.config", "rollup.config",
    "babel.config", "jest.config", "eslint.config", "prettier.config",
    "tailwind.config", "postcss.config", "next.config", "nuxt.config",
    "svelte.config", "astro.config", "vitest.config", ".vitepress",
]
