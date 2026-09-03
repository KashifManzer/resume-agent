"""T13 — screening answerer + answer bank: question_sig stability, heuristic +
LLM-mocked classify, the cache, the three-tier branch, and the honesty guards
(never-invent, never-auto, salary-blank, graceful degradation)."""

from fastapi.testclient import TestClient

from app import db
from app.canonical import ANSWER_CANONICAL
from app.main import app
from app.models import Answer, AnswerResolution
from app.routers.profile import PID
from app.services import answerer


def _fill(canonical: str, answer: str, mode: str = "verbatim") -> None:
    """Put a value in a seeded canonical-core row."""
    with db.SessionLocal() as s:
        a = s.query(Answer).filter_by(profile_id=PID, canonical=canonical).one()
        a.answer, a.mode = answer, mode
        s.commit()


def _no_llm(monkeypatch):
    """Guard: any LLM call in this path is a bug (verbatim/never-auto must not call it)."""
    def boom(*a, **k):
        raise AssertionError("LLM must not be called on this path")
    monkeypatch.setattr(answerer.llm, "chat", boom)


# --- question_sig -----------------------------------------------------------


def test_question_sig_is_normalized_stable():
    assert answerer.question_sig("Why this company?") == answerer.question_sig("why   this company")
    assert answerer.question_sig("Desired salary*") == answerer.question_sig("desired salary")
    assert answerer.question_sig("Salary") != answerer.question_sig("Notice period")


# --- seeding ----------------------------------------------------------------


def test_init_db_seeds_core_idempotently():
    with db.SessionLocal() as s:
        n1 = s.query(Answer).count()
    assert n1 == len(ANSWER_CANONICAL)
    db.init_db()  # second run seeds nothing new
    with db.SessionLocal() as s:
        assert s.query(Answer).count() == len(ANSWER_CANONICAL)


# --- heuristic classify -----------------------------------------------------


def test_heuristic_classifies_common_questions():
    h = answerer._heuristic
    assert h("What are your salary expectations?") == "salary_expectation"
    assert h("Are you authorized to work in the US?") == "work_authorization"
    assert h("Will you now or in future require visa sponsorship?") == "requires_sponsorship"
    assert h("Why do you want to work here?") == "why_company"
    assert h("Tell us about yourself") == "tell_me_about_yourself"
    assert h("What is your gender identity?") == "eeo_demographic"
    assert h("Have you ever been convicted of a felony?") == "criminal_background"
    assert h("What is your favorite programming language?") is None  # → LLM lane


# --- resolve: heuristic → LLM (mocked) → cache ------------------------------


def test_resolve_caches_classification(monkeypatch):
    calls = {"n": 0}

    def fake_classify(q):
        calls["n"] += 1
        return "why_company"

    monkeypatch.setattr(answerer, "_llm_classify", fake_classify)
    q = "What excites you about our unusual mission?"  # not heuristic-matchable
    with db.SessionLocal() as s:
        assert answerer.resolve("boards.greenhouse.io", q, s) == "why_company"
    with db.SessionLocal() as s:  # repeat → cache, no second LLM call
        assert answerer.resolve("boards.greenhouse.io", q, s) == "why_company"
    assert calls["n"] == 1
    with db.SessionLocal() as s:
        assert s.query(AnswerResolution).count() == 1


def test_resolve_llm_outage_does_not_poison_cache(monkeypatch):
    def boom(q):
        raise RuntimeError("ollama down")

    monkeypatch.setattr(answerer, "_llm_classify", boom)
    q = "Some bespoke question the heuristic misses"
    with db.SessionLocal() as s:
        assert answerer.resolve("h", q, s) is None
        assert s.query(AnswerResolution).count() == 0  # nothing cached


# --- three-tier branch ------------------------------------------------------


def test_verbatim_fills_bank_value_with_no_llm(monkeypatch):
    _no_llm(monkeypatch)
    _fill("salary_expectation", "$150,000")
    with db.SessionLocal() as s:
        r = answerer.answer("What is your desired salary?", None, "h", s)
    assert r.answer == "$150,000" and r.source == "bank_verbatim" and r.needs_review is False


def test_adaptable_tailors_the_template(monkeypatch):
    _fill("why_company", "I love building developer tools.", mode="adaptable")
    monkeypatch.setattr(answerer, "_llm_answer", lambda q, tmpl, jd, tex: f"[tailored] {tmpl}")
    with db.SessionLocal() as s:
        r = answerer.answer("Why do you want to work here?", None, "h", s)
    assert r.source == "bank_adapted" and r.needs_review is True and "tailored" in r.answer


def test_fresh_draft_when_no_match(monkeypatch):
    monkeypatch.setattr(answerer, "_llm_classify", lambda q: None)  # no canonical
    monkeypatch.setattr(answerer, "_llm_answer", lambda q, tmpl, jd, tex: "A grounded, drafted answer.")
    with db.SessionLocal() as s:
        r = answerer.answer("Describe a project you're proud of.", None, "h", s)
    assert r.source == "llm_fresh" and r.needs_review is True and r.answer


# --- honesty guards ---------------------------------------------------------


def test_never_invents_when_llm_returns_empty(monkeypatch):
    monkeypatch.setattr(answerer, "_llm_classify", lambda q: None)
    monkeypatch.setattr(answerer, "_llm_answer", lambda q, tmpl, jd, tex: "")  # nothing grounded
    with db.SessionLocal() as s:
        r = answerer.answer("How many years of Fortran do you have?", None, "h", s)
    assert r.answer == "" and r.source == "blank" and r.needs_review is True


def test_never_auto_eeo_left_blank_no_llm(monkeypatch):
    _no_llm(monkeypatch)  # must never reach the LLM
    with db.SessionLocal() as s:
        r = answerer.answer("What is your race/ethnicity?", "job1", "h", s)
    assert r.answer == "" and r.source == "blank" and r.canonical == "eeo_demographic"


def test_never_auto_uses_stored_answer_if_present(monkeypatch):
    _no_llm(monkeypatch)
    with db.SessionLocal() as s:  # user explicitly stored a veteran-status answer
        s.add(Answer(profile_id=PID, canonical="eeo_demographic", answer="Decline to state", mode="verbatim"))
        s.commit()
    with db.SessionLocal() as s:
        r = answerer.answer("Are you a protected veteran?", None, "h", s)
    assert r.answer == "Decline to state" and r.source == "bank_verbatim"


def test_salary_with_no_stored_value_is_blank(monkeypatch):
    _no_llm(monkeypatch)  # never guess a market number
    with db.SessionLocal() as s:
        r = answerer.answer("Desired salary?", None, "h", s)
    assert r.answer == "" and r.source == "blank" and r.canonical == "salary_expectation"


def test_graceful_degradation_verbatim_still_fills_when_llm_down(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("ollama down")

    monkeypatch.setattr(answerer.llm, "chat", boom)
    _fill("work_authorization", "US citizen")
    with db.SessionLocal() as s:
        r = answerer.answer("Are you authorized to work in the US?", None, "h", s)
    assert r.answer == "US citizen"  # verbatim path never needed the LLM


def test_graceful_degradation_llm_field_flags_couldnt_draft(monkeypatch):
    monkeypatch.setattr(answerer, "_llm_classify", lambda q: None)

    def boom(*a, **k):
        raise RuntimeError("ollama down")

    monkeypatch.setattr(answerer.llm, "chat", boom)
    with db.SessionLocal() as s:
        r = answerer.answer("Anything else to add?", "job1", "h", s)
    assert r.answer == "" and r.needs_review is True and "couldn't draft" in (r.reason or "")


# --- custom Q&A -------------------------------------------------------------


def test_custom_verbatim_entry_matches_by_question(monkeypatch):
    _no_llm(monkeypatch)  # a matched verbatim custom entry needs no LLM
    with db.SessionLocal() as s:
        s.add(Answer(profile_id=PID, canonical=None, question="Do you have a security clearance?",
                     answer="Yes — active Secret.", mode="verbatim"))
        s.commit()
    with db.SessionLocal() as s:
        r = answerer.answer("Do you have a security clearance?", None, "h", s)
    assert r.answer == "Yes — active Secret." and r.source == "bank_verbatim"


# --- CRUD + endpoint + privacy ----------------------------------------------


def test_answers_crud_and_seed_visible():
    c = TestClient(app)
    rows = c.get("/answers").json()
    assert len(rows) == len(ANSWER_CANONICAL)
    assert {r["canonical"] for r in rows} == set(ANSWER_CANONICAL)

    core = next(r for r in rows if r["canonical"] == "notice_period")
    up = c.put(f"/answers/{core['id']}", json={"answer": "2 weeks", "mode": "verbatim"})
    assert up.status_code == 200 and up.json()["answer"] == "2 weeks"
    assert c.delete(f"/answers/{core['id']}").status_code == 400  # core can't be deleted

    made = c.post("/answers", json={"question": "Preferred pronouns?", "answer": "they/them", "mode": "verbatim"})
    cid = made.json()["id"]
    assert made.status_code == 200 and made.json()["canonical"] is None
    assert c.post("/answers", json={"question": "  "}).status_code == 400  # custom needs a question
    assert c.delete(f"/answers/{cid}").status_code == 200


def test_autofill_answer_endpoint(monkeypatch):
    _fill("years_experience", "7 years")
    c = TestClient(app)
    r = c.post("/autofill/answer", json={"question": "How many years of experience?", "host": "h"})
    assert r.status_code == 200 and r.json()["answer"] == "7 years"


def test_answer_request_is_question_only():
    # Privacy: the request model carries ONLY question + job_id + host.
    from app.schemas.answer import AnswerRequest
    assert set(AnswerRequest.model_fields) == {"question", "job_id", "host"}


# --- T24: the adapt path re-grounds instead of preserving --------------------


def test_adapt_prompt_regrounds_on_current_resume_and_drops_unsupported(monkeypatch):
    """A saved template is a STYLE guide, not a fact carrier: résumés are
    re-tailored per job, so a claim template-A asserted may be absent from the
    résumé this recruiter reads. The prompt must say DROP it, not preserve it."""
    seen = {}

    def fake_chat(messages, format=None):
        seen["prompt"] = messages[1]["content"]
        return {"answer": "drafted"}

    monkeypatch.setattr(answerer.llm, "chat", fake_chat)
    answerer._llm_answer("Why us?", "I led a 40-person platform team.", "JD TEXT", "RESUME TEX")

    prompt = seen["prompt"]
    assert "RESUME TEX" in prompt  # re-grounded on THIS job's tailored résumé
    assert "DROP any template claim it does not support" in prompt
    assert "preserve every fact" not in prompt.lower()


def test_save_mode_defaults_by_category():
    assert answerer.save_mode("notice_period") == "verbatim"  # a fact about the person
    assert answerer.save_mode("why_company") == "adaptable"  # résumé-grounded prose
    assert answerer.save_mode(None) == "adaptable"  # fresh draft → never frozen
    assert answerer.save_mode("eeo_demographic") == "verbatim"  # never LLM-rewritten


def test_behavioral_questions_are_answered_not_refused(monkeypatch):
    """The never-invent guard is aimed at FACT lookups (certs, years, employers).
    A 'describe a project you led' question must draft from the résumé's real
    projects — refusing those made the answerer useless for the most common
    application questions."""
    seen = {}

    def fake_chat(messages, format=None):
        seen["system"] = messages[0]["content"]
        return {"answer": "drafted"}

    monkeypatch.setattr(answerer.llm, "chat", fake_chat)
    answerer._llm_answer("Describe a project you led.", "", "JD", "RESUME")

    system = seen["system"]
    assert "DESCRIBE or EXPLAIN" in system and "do not refuse" in system
    # the fact-lookup guard is still the trust boundary — it must stay narrow, not vanish
    assert "never invent experience, numbers" in system
    assert "empty answer ONLY when" in system
