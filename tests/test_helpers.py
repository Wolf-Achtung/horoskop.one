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

class TestMixerNormalization:
    def test_none_returns_balanced_default(self):
        m = main._normalize_mixer(None)
        assert sum(m.values()) == 100
        assert set(m.keys()) == {"astro", "num", "tarot", "iching", "cn", "tree"}

    def test_empty_dict_returns_default(self):
        assert sum(main._normalize_mixer({}).values()) == 100

    def test_already_summing_to_100_unchanged(self):
        src = {"astro": 60, "num": 10, "tarot": 5, "iching": 15, "cn": 5, "tree": 5}
        assert main._normalize_mixer(src) == src

    def test_oversum_is_rescaled_to_100(self):
        # 34+13+17+62+11+11 = 148 → rescale to 100
        out = main._normalize_mixer({"astro": 34, "num": 13, "tarot": 17, "iching": 62, "cn": 11, "tree": 11})
        assert sum(out.values()) == 100
        # I-Ging should still be the dominant weight after rescaling
        assert max(out.items(), key=lambda kv: kv[1])[0] == "iching"

    def test_negative_values_clamped(self):
        out = main._normalize_mixer({"astro": 100, "num": -50, "tarot": 0, "iching": 0, "cn": 0, "tree": 0})
        assert sum(out.values()) == 100
        assert out["num"] == 0
        assert out["astro"] == 100

    def test_all_zero_returns_default(self):
        out = main._normalize_mixer({"astro": 0, "num": 0, "tarot": 0, "iching": 0, "cn": 0, "tree": 0})
        assert sum(out.values()) == 100
        assert out["astro"] == 34  # default balanced weighting

    def test_garbage_values_coerced(self):
        out = main._normalize_mixer({"astro": "sixty", "num": None, "tarot": 50, "iching": 50, "cn": 0, "tree": 0})
        assert sum(out.values()) == 100


class TestToneDirective:
    def test_all_known_tones_return_nonempty(self):
        for tone in ("mystic_coach", "mystisch", "coach", "skeptisch"):
            assert len(main._tone_directive(tone)) > 20

    def test_unknown_tone_falls_back_to_default(self):
        assert main._tone_directive("quatsch") == main._tone_directive("mystic_coach")

    def test_none_falls_back_to_default(self):
        assert main._tone_directive(None) == main._tone_directive("mystic_coach")

    def test_tones_are_distinct(self):
        assert main._tone_directive("mystisch") != main._tone_directive("coach")
        assert main._tone_directive("skeptisch") != main._tone_directive("coach")


class TestMixerDirective:
    def test_empty_mixer_returns_empty(self):
        assert main._mixer_directive({}) == ""

    def test_mixer_orders_by_weight_descending(self):
        m = main._normalize_mixer({"astro": 5, "num": 5, "tarot": 5, "iching": 80, "cn": 3, "tree": 2})
        block = main._mixer_directive(m)
        # I-Ging must be the first tradition mentioned and be marked as dominant
        first_line = [l for l in block.split("\n") if l.startswith("- ")][0]
        assert "I-Ging" in first_line
        assert "**I-Ging**" in block


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
