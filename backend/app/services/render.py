import subprocess
import tempfile
from pathlib import Path

import pymupdf

from app.core.config import LATEXMK_BIN, LATEX_ENGINE
from app.schemas.render import Guards, RenderResult

MIN_TEXT_CHARS = 200  # LaTeX text layer below this ⇒ extraction almost certainly broke
MAX_BAD_RATIO = 0.01  # replacement/control-char share above this ⇒ garbled glyphs


def _compile_error(work: Path, proc: subprocess.CompletedProcess) -> str:
    """latexmk's stderr is terse; the real LaTeX error lives in resume.log
    (lines starting with '!'). Prefer those, fall back to captured output."""
    log = work / "resume.log"
    if log.exists():
        bangs = [ln for ln in log.read_text(errors="replace").splitlines() if ln.startswith("!")]
        if bangs:
            return "\n".join(bangs)
    return (proc.stderr or proc.stdout or "latexmk failed").strip()


def render_tex(
    tex: str,
    *,
    expect: list[str] | None = None,
    outdir: Path | None = None,
) -> RenderResult:
    """Compile `tex` with latexmk and run the three guards (compiles / clean
    extraction / single page). Never raises on a guard failure — every failure
    is reported in the returned RenderResult so callers can accept/reject/retry.
    """
    # ponytail: mkdtemp leaks when outdir is None; the OS reaps it. T6 passes a
    # job workdir when it needs to keep the PDF.
    work = Path(outdir) if outdir is not None else Path(tempfile.mkdtemp(prefix="render-"))
    work.mkdir(parents=True, exist_ok=True)
    tex_path = work / "resume.tex"
    tex_path.write_text(tex)

    proc = subprocess.run(
        [
            LATEXMK_BIN,
            f"-{LATEX_ENGINE}",
            "-interaction=nonstopmode",
            "-halt-on-error",
            f"-output-directory={work}",
            str(tex_path),
        ],
        capture_output=True,
        text=True,
    )
    pdf_path = work / "resume.pdf"
    compiles = proc.returncode == 0 and pdf_path.exists()

    if not compiles:
        return RenderResult(
            ok=False,
            pdf_path=None,
            page_count=None,
            text="",
            guards=Guards(compiles=False, extraction_clean=False, single_page=False),
            errors=[_compile_error(work, proc)],
        )

    with pymupdf.open(pdf_path) as doc:
        page_count = doc.page_count
        text = "\n".join(page.get_text() for page in doc)

    bad = sum(1 for c in text if c == "�" or (ord(c) < 32 and c not in "\t\n\r\f"))
    ratio = bad / len(text) if text else 1.0
    extraction_clean = (
        len(text) >= MIN_TEXT_CHARS
        and ratio < MAX_BAD_RATIO
        and all(anchor in text for anchor in (expect or []))
    )
    single_page = page_count == 1

    return RenderResult(
        ok=compiles and extraction_clean and single_page,
        pdf_path=pdf_path,
        page_count=page_count,
        text=text,
        guards=Guards(
            compiles=compiles,
            extraction_clean=extraction_clean,
            single_page=single_page,
        ),
        errors=[],
    )
