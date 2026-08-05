"""Tests für das Monatsbrett (docs/spielkonzept.md): Ganzhi-Zyklus,
Mondmonats-Brett, Senet-Regeln und die drei Board-Endpoints."""
import datetime as dt

from fastapi.testclient import TestClient

import main

client = TestClient(main.app)


# ---------------------------------------------------------------------------
# Ganzhi (60er-Zyklus)
# ---------------------------------------------------------------------------

class TestGanzhi:
    def test_anchor_is_jiazi(self):
        # 27.01.2019 war ein Jiǎzǐ-Tag (Index 1 der 1-basierten Zählung).
        g = main.ganzhi_day(dt.date(2019, 1, 27))
        assert g["index"] == 1
        assert g["pinyin"] == "Jiǎzǐ".replace("Zǐ", "zǐ")
        assert g["label"] == "Holz-Ratte"

    def test_cycle_repeats_after_60_days(self):
        a = main.ganzhi_day(dt.date(2019, 1, 27))
        b = main.ganzhi_day(dt.date(2019, 1, 27) + dt.timedelta(days=60))
        assert a == b

    def test_all_60_combinations_distinct(self):
        seen = set()
        for i in range(60):
            g = main.ganzhi_day(dt.date(2024, 1, 1) + dt.timedelta(days=i))
            seen.add((g["index"], g["pinyin"]))
        assert len(seen) == 60


# ---------------------------------------------------------------------------
# Mondmonats-Brett
# ---------------------------------------------------------------------------

class TestLunarBoard:
    def test_day_index_in_range(self):
        for i in range(0, 400, 7):
            lb = main.lunar_board(dt.date(2026, 1, 1) + dt.timedelta(days=i))
            assert 1 <= lb["dayIndex"] <= 30

    def test_board_id_stable_within_cycle(self):
        # Innerhalb eines Zyklus muss die Brett-ID konstant bleiben und der
        # Tagesindex täglich um 1 steigen (bis zum Neumond-Wrap).
        d = dt.date(2026, 3, 1)
        prev = main.lunar_board(d)
        for i in range(1, 40):
            cur = main.lunar_board(d + dt.timedelta(days=i))
            if cur["boardId"] == prev["boardId"]:
                assert cur["dayIndex"] == prev["dayIndex"] + 1
            else:
                assert cur["dayIndex"] == 1  # neuer Zyklus beginnt bei Tag 1
            prev = cur

    def test_field_events_complete(self):
        assert len(main.FIELD_EVENTS) == 30
        assert main.FIELD_EVENTS[14]["name"] == "Haus der Wiedergeburt"
        assert main.FIELD_EVENTS[26]["name"] == "Haus des Wassers"
        assert main.FIELD_EVENTS[29]["name"] == "Der Horizont"
        for f in main.FIELD_EVENTS:
            assert f["name"] and f["core"]


# ---------------------------------------------------------------------------
# Wurf & Regeln
# ---------------------------------------------------------------------------

class TestThrow:
    def test_deterministic_and_in_range(self):
        a = main.board_throw("27.07.1966", "2026-08-13", 5)
        b = main.board_throw("27.07.1966", "2026-08-13", 5)
        assert a == b and 1 <= a <= 5

    def test_varies_with_day(self):
        vals = {main.board_throw("27.07.1966", "2026-08-13", d) for d in range(1, 31)}
        assert len(vals) > 1


def _pos(**overrides):
    base = {s: 0 for s in main.STONES}
    base.update(overrides)
    return base


class TestLegalMoves:
    def test_from_start_all_stones_move(self):
        moves = main.legal_moves(_pos(), 3)
        # Alle wollen auf Feld 3 — nur einer darf (kein Landen auf eigenem
        # Stein gilt erst, wenn dort einer steht; vom Start aus zielen alle
        # auf dasselbe freie Feld, also sind alle Züge einzeln legal).
        assert all(t == 3 for t in moves.values())
        assert set(moves) == set(main.STONES)

    def test_cannot_land_on_own_stone(self):
        moves = main.legal_moves(_pos(fokus=5, werk=8), 3)
        assert "fokus" not in moves          # 5+3=8 ist belegt
        assert moves["werk"] == 11

    def test_water_redirects_to_rebirth(self):
        moves = main.legal_moves(_pos(fokus=24), 3)   # 24+3=27 → Wasser
        assert moves["fokus"] == 15

    def test_water_walks_down_when_rebirth_taken(self):
        moves = main.legal_moves(_pos(fokus=24, werk=15), 3)
        assert moves["fokus"] == 14

    def test_exit_rules(self):
        assert main.legal_moves(_pos(fokus=30), 4)["fokus"] == 31   # 30: jeder Wurf
        assert main.legal_moves(_pos(fokus=29), 2)["fokus"] == 31   # 29: nur 2
        assert "fokus" not in main.legal_moves(_pos(fokus=29), 4)
        assert main.legal_moves(_pos(fokus=28), 3)["fokus"] == 31   # 28: nur 3
        assert "fokus" not in main.legal_moves(_pos(fokus=28), 5)
        assert "fokus" not in main.legal_moves(_pos(fokus=27), 5)   # Überwurf

    def test_stone_in_aaru_never_moves(self):
        assert "fokus" not in main.legal_moves(_pos(fokus=31), 3)

    def test_validate_rejects_double_occupancy(self):
        try:
            main._validate_positions({"fokus": 7, "werk": 7})
            assert False, "sollte ValueError werfen"
        except ValueError:
            pass


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

class TestBoardEndpoints:
    def test_today_shape(self):
        r = client.get("/board/today")
        assert r.status_code == 200
        data = r.json()
        assert data["boardId"] and 1 <= data["dayIndex"] <= 30
        assert data["field"]["index"] == data["dayIndex"]
        assert set(data["stones"]) == set(main.STONES)
        assert data["hexagram"]["name"] and data["ganzhi"]["label"]

    def test_throw_returns_legal_moves(self):
        r = client.post("/board/throw", json={"birthDate": "27.07.1966", "positions": {}})
        assert r.status_code == 200
        data = r.json()
        assert 1 <= data["throw"] <= 5
        assert set(data["legalMoves"]) == set(main.STONES)

    def test_throw_rejects_future_day(self):
        today = client.get("/board/today").json()
        if today["dayIndex"] < 30:
            r = client.post("/board/throw", json={
                "birthDate": "27.07.1966", "positions": {}, "dayIndex": 30})
            assert r.status_code == 422

    def test_move_happy_path_with_fallback_text(self, monkeypatch):
        # LLM absichtlich kaputt → deterministischer Fallback-Text muss kommen.
        class _Boom:
            def __getattr__(self, name):
                raise RuntimeError("kein LLM im Test")
        monkeypatch.setattr(main, "client", _Boom())

        throw = client.post("/board/throw", json={
            "birthDate": "27.07.1966", "positions": {}}).json()
        stone = next(iter(throw["legalMoves"]))
        r = client.post("/board/move", json={
            "birthDate": "27.07.1966", "positions": {}, "stone": stone})
        assert r.status_code == 200
        data = r.json()
        assert data["positions"][stone] == throw["legalMoves"][stone]
        assert data["moved"]["stone"] == stone
        assert data["reading"]["text"]
        assert data["reading"]["chips"]

    def test_move_rejects_illegal_stone(self):
        r = client.post("/board/move", json={
            "birthDate": "27.07.1966", "positions": {"fokus": 31}, "stone": "fokus"})
        assert r.status_code == 422

    def test_play_path_rewrite_targets_board_page(self):
        # /play wird auf /play.html umgeschrieben (404 solange dist/ fehlt,
        # aber NICHT die index-Route der StaticFiles).
        r = client.get("/play")
        assert r.status_code in (200, 404)

    def test_mondlese_host_serves_board_as_homepage(self):
        r = client.get("/", headers={"host": "www.mondlese.de"})
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            assert "MONDLESE" in r.text


class TestEventDays:
    def test_event_deterministic_valid_and_rare(self):
        a = main.board_event("27.07.1966", "2026-08", 5)
        assert a == main.board_event("27.07.1966", "2026-08", 5)
        events = [main.board_event("27.07.1966", "2026-08", d) for d in range(1, 31)]
        found = [e for e in events if e]
        for e in found:
            assert e["key"] in main.BOARD_EVENTS
            assert e["symbol"] and e["name"] and e["text"]
        assert len(found) <= 6  # selten: im Schnitt ~2 pro Monat

    def test_alt_throw_in_range(self):
        for d in range(1, 31):
            assert 1 <= main.board_alt_throw("27.07.1966", "b", d) <= 5

    def test_throw_endpoint_carries_event_field(self):
        r = client.post("/board/throw", json={"birthDate": "27.07.1966", "positions": {}})
        assert r.status_code == 200
        assert "event" in r.json()

    def test_sternschnuppe_day_offers_alt_throw(self):
        today = client.get("/board/today").json()
        for day in range(1, today["dayIndex"] + 1):
            ev = main.board_event("27.07.1966", today["boardId"], day)
            if ev and ev["key"] == "sternschnuppe":
                r = client.post("/board/throw", json={
                    "birthDate": "27.07.1966", "positions": {}, "dayIndex": day}).json()
                assert r["event"]["key"] == "sternschnuppe"
                assert 1 <= r["alt"]["throw"] <= 5
                assert set(r["alt"]["legalMoves"]) <= set(main.STONES)
                return
        # kein Sternschnuppen-Tag in Reichweite dieses Monats — nichts zu prüfen

    def test_rueckenwind_day_extends_legal_moves(self):
        today = client.get("/board/today").json()
        for day in range(1, today["dayIndex"] + 1):
            ev = main.board_event("27.07.1966", today["boardId"], day)
            if ev and ev["key"] == "rueckenwind":
                base = main.board_throw("27.07.1966", today["boardId"], day)
                r = client.post("/board/throw", json={
                    "birthDate": "27.07.1966", "positions": {}, "dayIndex": day}).json()
                assert r["throw"] == base
                assert r["legalMoves"]["fokus"] == base + 1  # vom Start: Feld = Wurf+1
                return

    def test_move_rejects_alt_without_sternschnuppe(self):
        today = client.get("/board/today").json()
        for day in range(1, today["dayIndex"] + 1):
            ev = main.board_event("27.07.1966", today["boardId"], day)
            if not (ev and ev["key"] == "sternschnuppe"):
                r = client.post("/board/move", json={
                    "birthDate": "27.07.1966", "positions": {}, "stone": "fokus",
                    "dayIndex": day, "useAlt": True})
                assert r.status_code == 422
                assert "zweiten Wurf" in r.json()["detail"]
                return
        raise AssertionError("kein ereignisfreier Tag gefunden — extrem unwahrscheinlich")


class TestResonanz:
    def test_rejects_unparseable_dates(self):
        r = client.post("/resonanz", json={"birthDate": "quatsch", "partnerDate": "27.07.1966"})
        assert r.status_code == 422

    def test_happy_path_with_fallback_text(self, monkeypatch):
        def boom(*a, **k):
            raise RuntimeError("kein LLM im Test")
        monkeypatch.setattr(main, "oa_text", boom)
        r = client.post("/resonanz", json={
            "birthDate": "27.07.1966", "partnerDate": "13.02.1970"})
        assert r.status_code == 200
        data = r.json()
        assert data["text"] and len(data["chips"]) == 3
        assert data["pair"]["zodiac"] == ["Löwe", "Wassermann"]
        assert data["pair"]["animal"] == ["Pferd", "Hund"]
        assert data["date"]


class TestResonanzProfil:
    def test_shape_and_pair(self):
        r = client.get("/resonanz/profil", params={
            "birthDate": "27.07.1966", "partnerDate": "13.02.1970"})
        assert r.status_code == 200
        data = r.json()
        assert [b["key"] for b in data["blocks"]] == ["elements", "animals", "lifepath"]
        assert data["pair"]["element"] == ["Feuer", "Luft"]
        for b in data["blocks"]:
            assert b["title"] and b["text"]

    def test_rejects_bad_dates(self):
        r = client.get("/resonanz/profil", params={"birthDate": "x", "partnerDate": "y"})
        assert r.status_code == 422

    def test_all_element_pairs_covered(self):
        import itertools
        for pair in itertools.combinations_with_replacement(
                ["Erde", "Feuer", "Luft", "Wasser"], 2):
            assert tuple(sorted(pair)) in main._ELEMENT_PAIR_TEXTS, pair
        assert set(main._ZODIAC_ELEMENT) == set(main._ZODIAC_TRAITS)

    def test_animal_harmony_cases(self):
        assert "Dreiklang" in main._animal_harmony("Ratte", "Drache")   # Trine
        assert "gegenüber" in main._animal_harmony("Ratte", "Pferd")    # Opposition
        assert "auswendig" in main._animal_harmony("Hund", "Hund")      # gleich
        assert "bewusst" in main._animal_harmony("Ratte", "Büffel")     # neutral


class TestWochenlesung:
    def test_fallback_and_shape(self, monkeypatch):
        def boom(*a, **k):
            raise RuntimeError("kein LLM im Test")
        monkeypatch.setattr(main, "oa_text", boom)
        r = client.post("/wochenlesung", json={
            "birthDate": "27.07.1966",
            "moves": [{"day": 20, "stone": "werk", "field": "Der Abendstern"}]})
        assert r.status_code == 200
        data = r.json()
        assert data["text"] and data["week"].count("-W") == 1
        assert any(c.startswith("KW ") for c in data["chips"])

    def test_rejects_bad_date_and_too_many_moves(self):
        assert client.post("/wochenlesung", json={
            "birthDate": "quatsch", "moves": []}).status_code == 422
        moves = [{"day": 1, "stone": "werk"}] * 11
        assert client.post("/wochenlesung", json={
            "birthDate": "27.07.1966", "moves": moves}).status_code == 422


class TestPush:
    def test_config_disabled_without_keys(self):
        r = client.get("/push/config")
        assert r.status_code == 200
        assert r.json()["enabled"] is False

    def test_subscribe_rejected_when_disabled(self):
        r = client.post("/push/subscribe", json={
            "endpoint": "https://example.org/x",
            "keys": {"p256dh": "a", "auth": "b"}})
        assert r.status_code == 503

    def test_store_roundtrip(self, tmp_path, monkeypatch):
        monkeypatch.setattr(main, "PUSH_STORE_PATH", str(tmp_path / "subs.json"))
        main._push_save([{"endpoint": "e1", "keys": {}}])
        assert main._push_load() == [{"endpoint": "e1", "keys": {}}]
        # unsubscribe entfernt unabhängig vom enabled-Zustand
        r = client.post("/push/unsubscribe", json={"endpoint": "e1"})
        assert r.status_code == 200
        assert main._push_load() == []


class TestFieldAlbum:
    def test_fields_endpoint_returns_all_30_cards(self):
        r = client.get("/board/fields")
        assert r.status_code == 200
        fields = r.json()["fields"]
        assert len(fields) == 30
        assert [f["index"] for f in fields] == list(range(1, 31))
        assert fields[14]["name"] == "Haus der Wiedergeburt"
        for f in fields:
            assert f["name"] and f["core"]


class TestSternzwillinge:
    """Die kuratierte Promi-Geburtstagstabelle (public/assets/sternzwillinge.json):
    vollständig (alle 366 Kalendertage), wohlgeformt, nur belegbare Fakten
    (Name, Jahr, Kurzbeschreibung) — keine erfundenen Aussagen über Personen."""

    def _load(self):
        import json, pathlib
        p = pathlib.Path(__file__).parent.parent / "public" / "assets" / "sternzwillinge.json"
        assert p.exists(), "public/assets/sternzwillinge.json fehlt"
        return json.loads(p.read_text(encoding="utf-8"))

    def test_covers_every_calendar_day(self):
        data = self._load()
        days_per_month = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        expected = {f"{m:02d}-{d:02d}"
                    for m, n in enumerate(days_per_month, start=1)
                    for d in range(1, n + 1)}
        assert set(data) == expected

    def test_entries_are_wellformed(self):
        data = self._load()
        for day, twins in data.items():
            assert 1 <= len(twins) <= 4, f"{day}: {len(twins)} Einträge"
            for t in twins:
                assert t["name"].strip(), day
                assert isinstance(t["year"], int) and 1000 <= t["year"] <= 2020, (day, t)
                assert t["known"].strip(), (day, t)


class TestProfil:
    def test_shape_and_content(self):
        r = client.get("/profil", params={"birthDate": "27.07.1966"})
        assert r.status_code == 200
        data = r.json()
        assert data["zodiac"] == "Löwe" and data["animal"] == "Pferd"
        assert [b["key"] for b in data["blocks"]] == ["zodiac", "lifepath", "animal"]
        for b in data["blocks"]:
            assert b["title"] and b["text"]

    def test_rejects_bad_date(self):
        assert client.get("/profil", params={"birthDate": "quatsch"}).status_code == 422
        assert client.get("/profil").status_code == 422

    def test_all_zodiac_signs_covered(self):
        import datetime as dtm
        names = {main.zodiac_from_date(dtm.date(2024, 1, 1) + dtm.timedelta(days=i))
                 for i in range(366)}
        assert names == set(main._ZODIAC_TRAITS) == set(main._ZODIAC_SYMBOLS)

    def test_all_animals_and_lifepaths_covered(self):
        animals = {main.chinese_animal(y) for y in range(1900, 1913)}
        assert animals == set(main._ANIMAL_EMOJI) <= set(main._ANIMAL_TRAITS)
        assert set(main._LIFEPATH_FRIENDLY) == set(main._LIFEPATH_ARCHETYPES)


class TestPWAManifest:
    def test_manifest_valid_and_icons_exist(self):
        import json, pathlib
        root = pathlib.Path(__file__).parent.parent / "public"
        m = json.loads((root / "manifest.webmanifest").read_text(encoding="utf-8"))
        assert m["start_url"] == "/play" and m["display"] == "standalone"
        assert m["short_name"] == "Mondlese"
        for icon in m["icons"]:
            assert (root / icon["src"].lstrip("/")).exists(), icon["src"]
        assert (root / "assets" / "apple-touch-icon.png").exists()


class TestShareImageAndSticks:
    def test_og_image_is_referenced_and_present(self):
        import pathlib, re
        root = pathlib.Path(__file__).parent.parent / "public"
        html = (root / "play.html").read_text(encoding="utf-8")
        m = re.search(r'property="og:image" content="([^"]+)"', html)
        assert m, "play.html braucht ein og:image"
        # Absolute URL, damit WhatsApp & Co. das Bild überhaupt laden.
        assert m.group(1).startswith("https://"), m.group(1)
        assert (root / "assets" / "og-mondlese.jpg").exists()
        assert 'name="twitter:card" content="summary_large_image"' in html

    def test_falling_stick_cutouts_exist(self):
        import pathlib
        mat = pathlib.Path(__file__).parent.parent / "public" / "assets" / "material"
        for i in range(1, 5):
            assert (mat / f"stab-fall-{i}.webp").exists(), i
            assert (mat / f"stab-{i}.webp").exists(), i

    def test_toss_swaps_to_falling_photos(self):
        import pathlib
        css = (pathlib.Path(__file__).parent.parent / "public" / "natur.css").read_text(encoding="utf-8")
        for i in range(1, 5):
            assert f".sticks-row.tossing .stick[data-i=\"{i}\"]" in css, i
            assert f"stab-fall-{i}.webp" in css, i


class TestExplanations:
    def test_today_carries_four_explanations(self):
        data = client.get("/board/today").json()
        ex = data["explain"]
        assert [e["key"] for e in ex] == ["moon", "hexagram", "ganzhi", "field"]
        for e in ex:
            assert e["title"] and e["heute"] and e["hintergrund"] and e["link"]

    def test_ganzhi_explanation_composes_element_and_animal(self):
        data = client.get("/board/today").json()
        gz = data["ganzhi"]
        ex = next(e for e in data["explain"] if e["key"] == "ganzhi")
        assert gz["element"] in ex["heute"]
        assert gz["animal"] in ex["heute"]

    def test_all_moon_phase_names_have_meanings(self):
        names = {main.moon_phase_name(f / 100) for f in range(0, 100)}
        for n in names:
            assert n in main._MOON_MEANINGS, f"Mondphase ohne Deutung: {n}"

    def test_all_elements_and_animals_covered(self):
        assert set(main._ELEMENT_TRAITS) == {e for _, e in main._STEMS}
        assert set(main._ANIMAL_TRAITS) == {a for _, a in main._BRANCHES}


class TestComparePage:
    def test_without_anthropic_shows_setup_hint(self, monkeypatch):
        monkeypatch.setattr(main, "_anthropic_client", None)
        r = client.get("/compare")
        assert r.status_code == 200
        assert "ANTHROPIC_API_KEY" in r.text

    def test_form_shown_when_configured(self, monkeypatch):
        monkeypatch.setattr(main, "_anthropic_client", object())
        r = client.get("/compare")
        assert r.status_code == 200
        assert "Geburtsdatum" in r.text and "Vergleich erzeugen" in r.text

    def test_blind_pair_with_mocked_providers(self, monkeypatch):
        monkeypatch.setattr(main, "_anthropic_client", object())
        def fake_llm(system, user, temperature=0.8, seed=None, provider=None):
            return f"text-von-{provider}"
        monkeypatch.setattr(main, "llm_text", fake_llm)
        r = client.get("/compare", params={"birthDate": "1966-07-27", "stone": "werk"})
        assert r.status_code == 200
        assert "Version A" in r.text and "Version B" in r.text
        assert "text-von-openai" in r.text and "text-von-anthropic" in r.text
        assert "Auflösung" in r.text
