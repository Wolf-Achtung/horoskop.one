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


class TestNumerologyExtensions:
    def test_master_number_preserved(self):
        # 27.07.1966 → 1+9+6+6+7+2+7 = 38 → 11 (Meisterzahl) — must not reduce to 2
        assert main.life_path_number(dt.date(1966, 7, 27)) == 11

    def test_birthday_number_reduces(self):
        assert main.birthday_number(dt.date(1966, 7, 27)) == 9   # 2+7
        assert main.birthday_number(dt.date(1990, 1, 11)) == 11  # master preserved

    def test_personal_year_changes_with_year(self):
        bd = dt.date(1966, 7, 27)
        y2025 = main.personal_year_number(bd, dt.date(2025, 1, 1))
        y2026 = main.personal_year_number(bd, dt.date(2026, 1, 1))
        assert y2025 != y2026
        assert 1 <= y2025 <= 9 and 1 <= y2026 <= 9

    def test_personal_month_changes_with_month(self):
        bd = dt.date(1966, 7, 27)
        m1 = main.personal_month_number(bd, dt.date(2026, 1, 1))
        m6 = main.personal_month_number(bd, dt.date(2026, 6, 1))
        assert m1 != m6

    def test_personal_day_deterministic(self):
        bd = dt.date(1966, 7, 27)
        ref = dt.date(2026, 4, 8)
        assert main.personal_day_number(bd, ref) == main.personal_day_number(bd, ref)

    def test_lifepath_archetype_exists_for_common_numbers(self):
        for n in (1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 22, 33):
            assert len(main.lifepath_archetype(n)) > 10


class TestIChingTable:
    def test_table_has_all_64_hexagrams(self):
        # Index 0 is a placeholder, 1..64 are the real hexagrams
        assert len(main.ICHING_HEXAGRAMS) == 65
        for i in range(1, 65):
            h = main.ICHING_HEXAGRAMS[i]
            assert h.get("name"), f"Hexagram {i} missing name"
            assert h.get("core"), f"Hexagram {i} missing core"

    def test_iching_index_always_in_range(self):
        # Sample a year's worth of dates
        d = dt.date(2026, 1, 1)
        for i in range(366):
            idx = main.iching_index(d + dt.timedelta(days=i))
            assert 1 <= idx <= 64

    def test_iching_lookup_returns_name_and_core(self):
        info = main.iching_lookup(1)
        assert info["name"] == "Das Schöpferische"
        assert info["core"]

    def test_iching_lookup_out_of_range_returns_empty(self):
        assert main.iching_lookup(0)["name"] == ""
        assert main.iching_lookup(65)["name"] == ""


class TestTarotDraw:
    def test_major_arcana_has_22_cards(self):
        assert len(main.TAROT_MAJOR) == 22

    def test_draw_is_deterministic(self):
        bd = dt.date(1966, 7, 27)
        ref = dt.date(2026, 4, 8)
        a = main.tarot_draw(bd, "day", None, ref)
        b = main.tarot_draw(bd, "day", None, ref)
        assert a == b

    def test_draw_differs_by_period(self):
        bd = dt.date(1966, 7, 27)
        ref = dt.date(2026, 4, 8)
        day = main.tarot_draw(bd, "day", None, ref)
        week = main.tarot_draw(bd, "week", None, ref)
        month = main.tarot_draw(bd, "month", None, ref)
        # Not a hard requirement that all three differ, but at least two should,
        # otherwise the bucket hashing is broken.
        assert len({day["index"], week["index"], month["index"]}) >= 2

    def test_draw_differs_by_birthdate(self):
        ref = dt.date(2026, 4, 8)
        a = main.tarot_draw(dt.date(1966, 7, 27), "day", None, ref)
        b = main.tarot_draw(dt.date(1990, 1, 15), "day", None, ref)
        assert a["index"] != b["index"]

    def test_draw_has_required_fields(self):
        card = main.tarot_draw(dt.date(1966, 7, 27), "day", None, dt.date(2026, 4, 8))
        assert "name" in card and card["name"]
        assert "core" in card and card["core"]
        assert 0 <= card["index"] < 22


class TestPeriodBucket:
    def test_day_bucket_is_iso_date(self):
        assert main._period_bucket("day", dt.date(2026, 4, 8)) == "2026-04-08"

    def test_week_bucket_is_iso_week(self):
        b = main._period_bucket("week", dt.date(2026, 4, 8))
        # "2026-W15" or similar — prefix + zero-padded 2-digit week
        assert b.startswith("2026-W")
        week_part = b.split("W")[1]
        assert week_part.isdigit() and len(week_part) == 2

    def test_month_bucket_is_yyyy_mm(self):
        assert main._period_bucket("month", dt.date(2026, 4, 8)) == "2026-04"

    def test_unknown_period_falls_back_to_day(self):
        assert main._period_bucket("foo", dt.date(2026, 4, 8)) == "2026-04-08"


class TestCacheLayer:
    def test_cache_miss_returns_none(self):
        main._READING_CACHE.clear()
        assert main._cache_get("missing") is None

    def test_cache_roundtrip(self):
        main._READING_CACHE.clear()
        dummy = main.ReadingResponse(
            meta={"x": 1}, sections=[], chips=[], disclaimer=""
        )
        main._cache_put("k1", dummy)
        assert main._cache_get("k1") is dummy

    def test_cache_key_differs_by_period(self):
        a = main.ReadingRequest(birthDate="27.07.1966", birthPlace="Berlin", period="day")
        b = main.ReadingRequest(birthDate="27.07.1966", birthPlace="Berlin", period="week")
        assert main._cache_key(a) != main._cache_key(b)

    def test_cache_key_differs_by_mixer(self):
        a = main.ReadingRequest(birthDate="27.07.1966", birthPlace="Berlin",
                                mixer={"astro": 50, "num": 50})
        b = main.ReadingRequest(birthDate="27.07.1966", birthPlace="Berlin",
                                mixer={"astro": 10, "num": 90})
        assert main._cache_key(a) != main._cache_key(b)

    def test_cache_key_case_insensitive_place(self):
        a = main.ReadingRequest(birthDate="27.07.1966", birthPlace="Berlin")
        b = main.ReadingRequest(birthDate="27.07.1966", birthPlace="BERLIN")
        assert main._cache_key(a) == main._cache_key(b)


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
