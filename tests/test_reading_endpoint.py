"""Integration tests for POST /reading.

The OpenAI client is monkey-patched so the tests never hit the network.
"""
import asyncio
import json

import pytest

import main


class _MockChoice:
    def __init__(self, content: str):
        self.message = type("M", (), {"content": content})()


class _MockResp:
    def __init__(self, content: str):
        self.choices = [_MockChoice(content)]


class _MockCompletions:
    def __init__(self, content: str):
        self._content = content

    def create(self, **kwargs):
        return _MockResp(self._content)


class _MockChat:
    def __init__(self, content: str):
        self.completions = _MockCompletions(content)


class _MockClient:
    def __init__(self, content: str):
        self.chat = _MockChat(content)


@pytest.fixture
def mock_openai(monkeypatch):
    """Replace main.client with a mock that returns a fixed JSON payload."""
    def _install(content: str):
        monkeypatch.setattr(main, "client", _MockClient(content))
    return _install


@pytest.fixture(autouse=True)
def mock_geocode(monkeypatch):
    """Avoid hitting Nominatim in tests."""
    async def _fake(place):
        if place:
            return {"lat": 48.02, "lon": 9.5}
        return None
    monkeypatch.setattr(main, "geocode", _fake)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.new_event_loop().run_until_complete(coro)


def test_classic_reading_returns_expected_schema(mock_openai):
    classic_payload = json.dumps({
        "fokus": "Fokus-Absatz",
        "beruf": "Beruf-Absatz",
        "liebe": "Liebe-Absatz",
        "energie": "Energie-Absatz",
    })
    mock_openai(classic_payload)

    req = main.ReadingRequest(
        birthDate="27.07.1966",
        birthPlace="Bad Saulgau",
        birthTime="13:30",
        period="week",
        readingType="classic",
    )
    resp = _run(main._reading_impl(req))
    data = resp.model_dump()

    assert data["meta"]["readingType"] == "classic"
    assert data["meta"]["birthPlace"] == "Bad Saulgau"
    assert "mini" in data["meta"]
    assert data["meta"]["mini"]["sunSignApprox"] == "Löwe"

    # Mixer + tone surfacing: the meta must carry the normalized mixer and a
    # human-readable tone label so the UI can show them.
    assert "activeMixer" in data["meta"]
    assert sum(data["meta"]["activeMixer"].values()) == 100
    assert data["meta"]["toneLabel"]

    titles = [s["title"] for s in data["sections"]]
    assert titles == ["Fokus", "Beruf", "Liebe", "Energie"]
    assert all(s["chips"] for s in data["sections"])
    assert "Unterhaltung" in data["disclaimer"]


def test_mixer_weights_propagate_to_prompt(mock_openai, monkeypatch):
    """The raw mixer input must influence the prompt sent to OpenAI.

    We capture the prompt the mock client receives and assert that the
    dominant tradition is referenced as such.
    """
    seen = {"messages": None, "prompt": None}

    class _Capture:
        def create(self, **kwargs):
            # Classic reading uses oa_text() which passes `prompt=...`.
            seen["prompt"] = kwargs.get("prompt") or (kwargs.get("messages") or [{}])[-1].get("content", "")
            seen["messages"] = kwargs.get("messages")
            return _MockResp(json.dumps({"fokus": "f", "beruf": "b", "liebe": "l", "energie": "e"}))

    monkeypatch.setattr(main, "client", type("C", (), {"chat": type("X", (), {"completions": _Capture()})()})())

    req = main.ReadingRequest(
        birthDate="27.07.1966",
        birthPlace="Bad Saulgau",
        period="week",
        readingType="classic",
        tone="mystisch",
        mixer={"astro": 5, "num": 5, "tarot": 5, "iching": 80, "cn": 3, "tree": 2},
    )
    resp = _run(main._reading_impl(req))
    data = resp.model_dump()

    # I-Ging must dominate after normalization, and the prompt must reflect it.
    assert data["meta"]["activeMixer"]["iching"] >= 75
    combined = (seen["prompt"] or "") + json.dumps(seen["messages"] or [])
    assert "I-Ging" in combined
    assert "poetisch-mystisch" in combined or "mystisch" in combined.lower()


@pytest.mark.parametrize("rtype,expected_section_count", [
    ("blueprint", 5),
    ("soul_purpose", 5),
    ("career", 6),
    ("relationship", 5),
    ("wealth", 5),
    ("timeline", 6),
    ("genius", 6),
])
def test_deep_readings_return_expected_sections(mock_openai, rtype, expected_section_count):
    """Every deep-reading type must return the number of sections declared in
    _deep_section_map(), even if the AI output is a minimal JSON object."""
    # Provide all known keys as a safety net; unused ones are simply ignored.
    dummy = json.dumps({
        "persoenlichkeit": "p", "staerken": "s", "schwaechen": "w",
        "lebensaufgabe": "la", "tagesimpuls": "ti",
        "kernmission": "km", "lektionen": "lk", "weltbeitrag": "wb",
        "alltagsausrichtung": "aa", "affirmation": "af",
        "talente": "tl",
        "pfad_1": {"titel": "A", "beschreibung": "a"},
        "pfad_2": {"titel": "B", "beschreibung": "b"},
        "pfad_3": {"titel": "C", "beschreibung": "c"},
        "meiden": {"feld": "M", "grund": "g"},
        "naechster_schritt": "ns",
        "liebesstil": "ls", "kompatibilitaet": "kt",
        "liebeslektionen": "ll", "idealer_partner": "ip", "beziehungsimpuls": "bi",
        "geld_persoenlichkeit": "gp", "blockaden": "bl",
        "wohlstandsstrategie": "ws", "chancen_zeitfenster": "cz", "geld_ritual": "gr",
        "vergangene_phase": "vp", "aktuelle_phase": "ap",
        "wendepunkt": "wp", "jahr_1_2": "j12", "jahr_3_5": "j35", "vision": "v",
        "einzigartiges_talent": "et", "warum_dieses_talent": "wt",
        "schritt_1": {"titel": "S1", "beschreibung": "s1"},
        "schritt_2": {"titel": "S2", "beschreibung": "s2"},
        "schritt_3": {"titel": "S3", "beschreibung": "s3"},
        "meisterschafts_vision": "mv",
    })
    mock_openai(dummy)

    req = main.ReadingRequest(
        birthDate="27.07.1966",
        birthPlace="Bad Saulgau",
        period="week",
        readingType=rtype,
    )
    resp = _run(main._reading_impl(req))
    data = resp.model_dump()

    assert data["meta"]["readingType"] == rtype
    assert len(data["sections"]) == expected_section_count
    # Every section must have a non-empty title and a string body
    for s in data["sections"]:
        assert s["title"]
        assert isinstance(s["text"], str)


def test_second_identical_request_is_served_from_cache(mock_openai):
    """Two consecutive calls with identical inputs must hit the cache on the
    second call — cache-hit meta must flip to True and OpenAI must not be
    called a second time."""
    main._READING_CACHE.clear()
    call_count = {"n": 0}

    class _CountingCompletions:
        def create(self, **kwargs):
            call_count["n"] += 1
            return _MockResp(json.dumps({"fokus": "f", "beruf": "b", "liebe": "l", "energie": "e"}))

    import pytest
    # Install a counting mock
    main.client = type("C", (), {"chat": type("X", (), {"completions": _CountingCompletions()})()})()

    req = main.ReadingRequest(
        birthDate="27.07.1966", birthPlace="Bad Saulgau",
        period="day", readingType="classic",
    )
    r1 = _run(main._reading_impl(req)).model_dump()
    first_calls = call_count["n"]
    r2 = _run(main._reading_impl(req)).model_dump()
    # The second request must not increment the OpenAI call count at all.
    assert call_count["n"] == first_calls, "cache hit must skip OpenAI entirely"
    assert first_calls >= 1  # sanity: the first request did hit OpenAI
    assert r2["meta"].get("cacheHit") is True
    # Same content on both
    assert r1["sections"][0]["text"] == r2["sections"][0]["text"]


def test_classic_meta_includes_enriched_symbols(mock_openai):
    """The enriched meta.mini must carry the new symbols (I-Ging name,
    Tarot card, personal year etc.) so the UI can render rich chips."""
    mock_openai(json.dumps({"fokus": "f", "beruf": "b", "liebe": "l", "energie": "e"}))
    main._READING_CACHE.clear()
    req = main.ReadingRequest(
        birthDate="27.07.1966", birthPlace="Bad Saulgau",
        period="week", readingType="classic",
    )
    data = _run(main._reading_impl(req)).model_dump()
    mini = data["meta"]["mini"]
    assert mini["iChingName"]            # hexagram has a German name
    assert mini["iChingCore"]
    assert mini["lifePathArchetype"]     # numerology archetype present
    assert "personalYear" in mini
    assert "tarot" in mini and mini["tarot"].get("name")


def test_fallback_on_exception(monkeypatch):
    """If OpenAI raises, the endpoint must still return a valid
    ReadingResponse with meta.error set instead of a 500."""
    class _Boom:
        def __getattr__(self, name):
            raise RuntimeError("kaboom")

    monkeypatch.setattr(main, "client", _Boom())

    req = main.ReadingRequest(
        birthDate="27.07.1966",
        birthPlace="Bad Saulgau",
        period="day",
        readingType="classic",
    )
    resp = _run(main._reading_impl(req))
    data = resp.model_dump()

    # The endpoint must not crash
    assert "sections" in data
    assert isinstance(data["sections"], list)
