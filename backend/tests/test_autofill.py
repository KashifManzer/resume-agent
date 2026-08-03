"""T12 Phase 2 — /autofill/map field mapping: form_sig stability, heuristic
lane, LLM fallback (mocked), self-building cache, canonical vocab, and the
structure-only privacy boundary."""

from fastapi.testclient import TestClient

from app import db
from app.canonical import CANONICAL
from app.main import app
from app.schemas.autofill import FieldDescriptor
from app.services import field_map, llm


def fd(field_ref, **kw):
    return FieldDescriptor(field_ref=field_ref, **kw)


# --- form_sig ---------------------------------------------------------------


def test_form_sig_is_order_independent_and_whitespace_stable():
    a = [fd(0, name="email", type="email"), fd(1, name="name", label="Full  name")]
    b = [fd(9, name="name", label="Full name"), fd(4, name="email", type="email")]  # reordered + ws + refs
    assert field_map.form_sig(a) == field_map.form_sig(b)


def test_form_sig_changes_when_a_field_changes():
    a = [fd(0, name="email", type="email")]
    b = [fd(0, name="phone", type="tel")]
    assert field_map.form_sig(a) != field_map.form_sig(b)


# --- heuristic lane ---------------------------------------------------------


def test_heuristic_resolves_common_fields_without_llm():
    assert field_map.heuristic_map(fd(0, type="email"))[0] == "email"
    assert field_map.heuristic_map(fd(0, autocomplete="given-name"))[0] == "first_name"
    assert field_map.heuristic_map(fd(0, name="urls[LinkedIn]", label="LinkedIn URL"))[0] == "linkedin"
    assert field_map.heuristic_map(fd(0, tag="textarea", label="Anything else?"))[0] == "free_text"
    assert field_map.heuristic_map(fd(0, name="q", label="Referral code")) is None  # → LLM lane


def test_heuristic_handles_ashby_shapes():
    assert field_map.heuristic_map(fd(0, id="_systemfield_name", label="Name"))[0] == "full_name"
    assert field_map.heuristic_map(fd(0, id="_systemfield_resume", type="file", label="Resume"))[0] == "resume_upload"
    assert field_map.heuristic_map(fd(0, type="file")) is None  # anonymous autofill dropzone → not résumé


def test_heuristic_handles_workday_automation_ids():
    # Workday's hard case: automation-id is the only signal (no name/id/label).
    m = field_map.heuristic_map
    assert m(fd(0, data_automation_id="legalNameSection_firstName"))[0] == "first_name"
    assert m(fd(0, data_automation_id="legalNameSection_lastName"))[0] == "last_name"
    assert m(fd(0, data_automation_id="email"))[0] == "email"
    assert m(fd(0, data_automation_id="phone-number"))[0] == "phone"
    assert m(fd(0, data_automation_id="addressSection_city"))[0] == "location"
    assert m(fd(0, type="file", data_automation_id="file-upload-input-ref"))[0] == "resume_upload"


# --- resolve: heuristic → LLM (mocked) → cache ------------------------------


def test_resolve_heuristic_then_llm_then_cache(monkeypatch):
    calls = {"n": 0}

    def fake_llm(unresolved):
        calls["n"] += 1
        return {f.field_ref: "years_experience" for f in unresolved}

    monkeypatch.setattr(field_map, "_llm_map", fake_llm)
    fields = [
        fd(0, type="email"),  # heuristic → email
        fd(1, name="q1", label="How long have you been coding professionally?"),  # LLM → years_experience
    ]
    with db.SessionLocal() as s:
        first = {m.field_ref: m for m in field_map.resolve("boards.greenhouse.io", fields, s)}
    assert first[0].canonical == "email" and first[0].source == "heuristic"
    assert first[1].canonical == "years_experience" and first[1].source == "llm"
    assert calls["n"] == 1

    with db.SessionLocal() as s:  # identical form again → cache, no LLM
        second = field_map.resolve("boards.greenhouse.io", fields, s)
    assert all(m.source == "cache" for m in second)
    assert calls["n"] == 1


def test_llm_output_coerced_to_vocab(monkeypatch):
    monkeypatch.setattr(llm, "chat", lambda *a, **k: {"mappings": [{"field_ref": 0, "canonical": "hobbies"}]})
    out = field_map._llm_map([fd(0, label="Favorite hobby")])
    assert out[0] == "unknown"  # not in CANONICAL → coerced


def test_canonical_vocab_shape():
    assert "unknown" in CANONICAL and "free_text" in CANONICAL and "resume_upload" in CANONICAL
    assert "years_experience" in CANONICAL


# --- endpoint + privacy -----------------------------------------------------


def test_autofill_map_endpoint(monkeypatch):
    monkeypatch.setattr(field_map, "_llm_map", lambda un: {f.field_ref: "unknown" for f in un})
    c = TestClient(app)
    body = {
        "host": "jobs.lever.co",
        "fields": [
            {"field_ref": 0, "type": "email"},
            {"field_ref": 1, "name": "urls[LinkedIn]", "label": "LinkedIn URL"},
        ],
    }
    r = c.post("/autofill/map", json=body)
    assert r.status_code == 200
    m = {x["field_ref"]: x for x in r.json()["mappings"]}
    assert m[0]["canonical"] == "email"
    assert m[1]["canonical"] == "linkedin"


def test_descriptor_schema_is_structure_only():
    # Privacy trust boundary: the request model can carry ONLY field structure —
    # never a filled value and never page HTML. `context` (T19) is nearby
    # heading/legend TEXT — structural, still never a value.
    allowed = {
        "field_ref", "tag", "type", "name", "id",
        "autocomplete", "aria_label", "placeholder", "label", "data_automation_id", "required",
        "context",
    }
    assert set(FieldDescriptor.model_fields) == allowed
    assert "value" not in FieldDescriptor.model_fields


def test_llm_lane_feeds_structural_context(monkeypatch):
    # T19: an ambiguous label the heuristic can't resolve is disambiguated by the
    # structure-only `context` (section heading) — which must reach the LLM prompt.
    captured = {}

    def fake_chat(messages, **kw):
        captured["user"] = messages[-1]["content"]
        return {"mappings": [{"field_ref": 0, "canonical": "work_authorization"}]}

    monkeypatch.setattr(llm, "chat", fake_chat)
    out = field_map._llm_map([fd(0, label="Status", context="Work Authorization")])
    assert out[0] == "work_authorization"
    assert "Work Authorization" in captured["user"]  # context fed to the LLM lane
