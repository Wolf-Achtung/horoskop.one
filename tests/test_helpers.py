"""Unit tests for pure helpers in main.py.

These tests avoid any network or OpenAI calls — they only cover date parsing,
zodiac derivation, numerology, moon phases, seasons, I-Ging and Celtic trees.
"""
import datetime as dt

import main


# ---------------------------------------------------------------------------
# parse_birth_date
# ---------------------------------------------------------------------------

class TestParseBirthDate:
    def test_iso_format(self):
        assert main.parse_birth_date("1966-07-27") == dt.date(1966, 7, 27)

    def test_german_format(self):
        assert main.parse_birth_date("27.07.1966") == dt.date(1966, 7, 27)

    def test_german_two_digit_year_1900(self):
        # years >= 30 are interpreted as 19xx
        assert main.parse_birth_date("27.07.66") == dt.date(1966, 7, 27)

    def test_german_two_digit_year_2000(self):
        # years < 30 are interpreted as 20xx
        assert main.parse_birth_date("01.01.05") == dt.date(2005, 1, 1)

    def test_empty_returns_none(self):
        assert main.parse_birth_date("") is None
        assert main.parse_birth_date(None) is None

    def test_garbage_returns_none(self):
        assert main.parse_birth_date("not a date") is None
        assert main.parse_birth_date("2024/01/01") is None


# ---------------------------------------------------------------------------
# parse_birth_time
# ---------------------------------------------------------------------------

class TestParseBirthTime:
    def test_valid_time(self):
        assert main.parse_birth_time("14:30") == dt.time(14, 30)

    def test_single_digit_hour(self):
        assert main.parse_birth_time("9:05") == dt.time(9, 5)

    def test_clamps_out_of_range_hour(self):
        # 25:00 becomes 23:00 (clamped)
        assert main.parse_birth_time("25:00") == dt.time(23, 0)

    def test_clamps_out_of_range_minute(self):
        assert main.parse_birth_time("12:99") == dt.time(12, 59)

    def test_invalid_format_returns_none(self):
        assert main.parse_birth_time("") is None
        assert main.parse_birth_time(None) is None
        assert main.parse_birth_time("14h30") is None
        assert main.parse_birth_time("noon") is None


# ---------------------------------------------------------------------------
# zodiac / numerology / chinese / tree
# ---------------------------------------------------------------------------

class TestZodiac:
    def test_leo_boundary(self):
        assert main.zodiac_from_date(dt.date(1966, 7, 27)) == "Löwe"

    def test_aries_start(self):
        assert main.zodiac_from_date(dt.date(2000, 3, 21)) == "Widder"

    def test_capricorn_year_end(self):
        assert main.zodiac_from_date(dt.date(2000, 12, 31)) == "Steinbock"

    def test_aquarius(self):
        assert main.zodiac_from_date(dt.date(2000, 2, 1)) == "Wassermann"


class TestChinese:
    def test_dragon_year(self):
        assert main.chinese_animal(2024) == "Drache"

    def test_horse_year(self):
        assert main.chinese_animal(1966) == "Pferd"

    def test_rat_year(self):
        assert main.chinese_animal(2020) == "Ratte"


class TestLifePath:
    def test_master_number_11_preserved(self):
        # 1966-07-27 -> 1+9+6+6+0+7+2+7 = 38 -> 3+8 = 11 (master)
        assert main.life_path_number(dt.date(1966, 7, 27)) == 11

    def test_reduces_to_single_digit(self):
        # simple reducer, no master
        n = main.life_path_number(dt.date(2000, 1, 1))
        assert 1 <= n <= 9 or n in (11, 22, 33)


class TestCelticTree:
    def test_stechpalme_summer(self):
        assert main.celtic_tree(dt.date(1966, 7, 27)) == "Stechpalme"

    def test_birke_near_solstice(self):
        assert main.celtic_tree(dt.date(2000, 1, 1)) == "Birke"


# ---------------------------------------------------------------------------
# moon phase + season + i-ching
# ---------------------------------------------------------------------------

class TestMoonPhase:
    def test_fraction_in_unit_interval(self):
        for y in (1950, 2000, 2024):
            f = main.moon_phase_fraction(dt.date(y, 6, 15))
            assert 0.0 <= f < 1.0

    def test_phase_names_cover_full_cycle(self):
        names = {main.moon_phase_name(f / 100) for f in range(0, 100)}
        # should produce more than just one name across the cycle
        assert len(names) >= 4


class TestSeason:
    def test_north_summer(self):
        assert main.season_from_date_hemisphere(dt.date(2024, 7, 15), lat=52.5) == "Sommer"

    def test_south_summer_in_december(self):
        assert main.season_from_date_hemisphere(dt.date(2024, 12, 15), lat=-33.0) == "Sommer"

    def test_defaults_to_north_when_lat_none(self):
        assert main.season_from_date_hemisphere(dt.date(2024, 7, 15), lat=None) == "Sommer"


class TestIChing:
    def test_index_in_range(self):
        for d in (dt.date(2000, 1, 1), dt.date(2024, 6, 15), dt.date(1966, 7, 27)):
            idx = main.iching_index(d)
            assert 1 <= idx <= 64


# ---------------------------------------------------------------------------
# FastAPI routes exist
# ---------------------------------------------------------------------------

class TestRoutes:
    def test_reading_route_registered(self):
        paths = {getattr(r, "path", None) for r in main.app.routes}
        assert "/reading" in paths
        assert "/readings" in paths
        assert "/reading-types" in paths
        assert "/health" in paths
        assert "/healthz" in paths

    def test_reading_types_payload(self):
        types = main.reading_types()
        ids = {t["id"] for t in types}
        assert "classic" in ids
        assert "blueprint" in ids
        assert "genius" in ids
        assert len(types) == 8
