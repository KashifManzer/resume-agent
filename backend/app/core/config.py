import os

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
