import os
from pathlib import Path

# LaTeX toolchain; override via env for Docker/deploy where it lives elsewhere.
LATEXMK_BIN = os.environ.get("LATEXMK_BIN", "latexmk")
LATEX_ENGINE = os.environ.get("LATEX_ENGINE", "pdflatex")  # -lualatex/-xelatex for fontspec

# Ollama Cloud (shared LLM client). OLLAMA_API_KEY is required for any LLM call.
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "https://ollama.com")
OLLAMA_API_KEY = os.environ.get("OLLAMA_API_KEY")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:31b-cloud")

# ATS blend: weight on grounded keyword coverage vs the LLM fit judge.
ATS_COVERAGE_WEIGHT = float(os.environ.get("ATS_COVERAGE_WEIGHT", "0.6"))

# Selector: best score below this (0-100) → pick closest but warn "none close".
CLOSE_THRESHOLD = int(os.environ.get("CLOSE_THRESHOLD", "40"))

# Improver: retries when an edit fails to compile / exceeds one page.
IMPROVER_COMPILE_RETRIES = int(os.environ.get("IMPROVER_COMPILE_RETRIES", "2"))

# Orchestrator loops + quality gate (design §9).
INNER_LOOP_MAX = int(os.environ.get("INNER_LOOP_MAX", "3"))  # improver ↔ ATS, the only optimization loop
OUTER_LOOP_MAX = int(os.environ.get("OUTER_LOOP_MAX", "5"))  # user-feedback rounds
TARGET_ATS = int(os.environ.get("TARGET_ATS", "92"))  # inner loop stops early at/above this
HIRING_AGENT_GATE = float(os.environ.get("HIRING_AGENT_GATE", "80"))  # gate + advice, never looped
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")  # hiring-agent GitHub enrichment (60→5000 req/hr)
HIRING_AGENT_DIR = Path(
    os.environ.get("HIRING_AGENT_DIR", str(Path(__file__).resolve().parents[3] / "vendor" / "hiring-agent"))
)
