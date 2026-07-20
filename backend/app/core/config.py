import os

# LaTeX toolchain; override via env for Docker/deploy where it lives elsewhere.
LATEXMK_BIN = os.environ.get("LATEXMK_BIN", "latexmk")
LATEX_ENGINE = os.environ.get("LATEX_ENGINE", "pdflatex")  # -lualatex/-xelatex for fontspec
