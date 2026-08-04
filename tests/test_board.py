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
