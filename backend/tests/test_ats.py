import ast
import os
from pathlib import Path

import pytest

from app.schemas.ats import JdKeyword
from app.services import ats

FIXTURES = Path(__file__).parent / "fixtures"


def _kw(term, aliases=(), required=True):
    return JdKeyword(term=term, aliases=list(aliases), required=required)


# --- keyword_coverage: pure / deterministic --------------------------------


def test_coverage_matched_and_missing():
    kws = [_kw("Python"), _kw("Rust"), _kw("Kafka")]
    pct, matched, missing = ats.keyword_coverage(kws, "I ship Python and Kafka services.")
    assert matched == ["Python", "Kafka"]
    assert missing == ["Rust"]
    assert pct == pytest.approx(2 / 3)


def test_alias_match():
    kws = [_kw("Kubernetes", ["k8s"]), _kw("CI/CD", ["cicd", "ci cd"])]
    pct, matched, missing = ats.keyword_coverage(kws, "Ran k8s in prod with a cicd pipeline.")
    assert matched == ["Kubernetes", "CI/CD"]
    assert missing == []
    assert pct == 1.0


def test_case_insensitive():
    _, matched, _ = ats.keyword_coverage([_kw("PostgreSQL")], "used POSTGRESQL heavily")
    assert matched == ["PostgreSQL"]


def test_word_boundary_no_substring_false_positive():
    # "Go" must not match inside "Google"; standalone "go" must match.
    _, _, missing = ats.keyword_coverage([_kw("Go")], "I love Google Docs.")
    assert missing == ["Go"]
    _, matched, _ = ats.keyword_coverage([_kw("Go")], "I write Go daily.")
    assert matched == ["Go"]


def test_only_required_counted():
    kws = [_kw("Python", required=True), _kw("Rust", required=False)]
    pct, matched, missing = ats.keyword_coverage(kws, "Python only here.")
    assert pct == 1.0  # Rust is nice-to-have, absent but ignored
    assert missing == []
    assert matched == ["Python"]


def test_no_required_keywords_is_full_coverage():
    pct, matched, missing = ats.keyword_coverage([_kw("x", required=False)], "anything")
    assert (pct, matched, missing) == (1.0, [], [])


# --- score_ats orchestration: blend, gap list, clamp (LLM parts stubbed) ----


def test_blend_gap_and_scale(monkeypatch):
    kws = [_kw("Python"), _kw("Rust")]
    monkeypatch.setattr(ats, "extract_jd_keywords", lambda jd: kws)
    monkeypatch.setattr(ats, "llm_fit", lambda jd, r: (80, "solid fit"))
    result = ats.score_ats("jd", "I write Python daily.")
    # coverage 0.5 -> 50; blend w=0.6: 0.6*50 + 0.4*80 = 62
    assert result.overall == 62
    assert result.keyword_coverage == pytest.approx(0.5)
    assert result.matched == ["Python"]
    assert result.missing == ["Rust"]
    assert result.required_keywords == ["Python", "Rust"]
    assert result.rationale == "solid fit"


def test_overall_clamped_to_100(monkeypatch):
    monkeypatch.setattr(ats, "extract_jd_keywords", lambda jd: [_kw("Python")])
    monkeypatch.setattr(ats, "llm_fit", lambda jd, r: (150, ""))  # out-of-range on purpose
    assert ats.score_ats("jd", "Python").overall == 100


def test_ats_does_not_import_improver():
    tree = ast.parse(Path(ats.__file__).read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imported.update(a.name for a in node.names)
    assert not any("improver" in name for name in imported)


# --- live integration (needs real Ollama Cloud key) ------------------------


@pytest.mark.skipif(not os.getenv("OLLAMA_API_KEY"), reason="OLLAMA_API_KEY not set")
def test_live_score_ats():
    jd = (FIXTURES / "jd_sample.txt").read_text()
    resume = (FIXTURES / "resume_sample.txt").read_text()
    result = ats.score_ats(jd, resume)
    assert 0 <= result.overall <= 100
    assert isinstance(result.missing, list)
    assert result.rationale.strip()
    # DevOps JD must surface infra keywords
    terms = " ".join(result.required_keywords).lower()
    assert "kubernetes" in terms or "terraform" in terms
