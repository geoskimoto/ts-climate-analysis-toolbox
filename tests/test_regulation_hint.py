"""Tests for climate_core.catalog.regulation.regulation_hint (name/size heuristic).

Written from docs/baseflow_app_plan.md ("Regulation hint"). Pure-function tests;
no I/O.
"""

import dataclasses
import math

import pytest

from climate_core.catalog.regulation import RegulationHint, regulation_hint

REGULATED = "likely_regulated"
UNREGULATED = "likely_unregulated"
UNKNOWN = "unknown"


# --------------------------------------------------------------------------- #
# Dataclass shape
# --------------------------------------------------------------------------- #
def test_regulation_hint_is_frozen_dataclass_with_level_and_reason():
    assert dataclasses.is_dataclass(RegulationHint)
    assert [f.name for f in dataclasses.fields(RegulationHint)] == ["level", "reason"]
    h = RegulationHint(level=UNKNOWN, reason="x")
    with pytest.raises(dataclasses.FrozenInstanceError):
        h.level = REGULATED  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        h.reason = "y"  # type: ignore[misc]


def test_return_type_and_level_vocabulary():
    for name, area in [("SNAKE RIVER BELOW X", 10), ("PLAIN CR", 10), ("PLAIN CR", 5000), (None, None)]:
        h = regulation_hint(name, area)
        assert isinstance(h, RegulationHint)
        assert h.level in {REGULATED, UNREGULATED, UNKNOWN}
        assert isinstance(h.reason, str) and h.reason


# --------------------------------------------------------------------------- #
# Each name pattern -> likely_regulated (large area so area cannot explain it)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "name, needle",
    [
        ("NORTH FORK DAM", "DAM"),
        ("SNAKE RIVER BELOW HELLS CANYON", "BELOW"),
        ("CLARK FORK BL MISSOULA", "BL"),
        ("OWYHEE RESERVOIR NR ADRIAN", "RESERVOIR"),
        ("OWYHEE RESERVOIRS NR ADRIAN", "RESERVOIR"),
        ("MAIN CANAL NR BURLEY", "CANAL"),
        ("SOUTH SIDE CANALS NR BURLEY", "CANAL"),
        ("YAKIMA R DIVERSION NR PROSSER", "DIVERSION"),
        ("TWIN FALLS DIVERSIONS", "DIVERSION"),
        ("BIG FLUME NR TOWN", "FLUME"),
        ("SMALL FLUMES NR TOWN", "FLUME"),
        ("PAYETTE LAKE OUTLET NR MCCALL", "LAKE OUTLET"),
        ("MILNER WASTEWAY NR BURLEY", "WASTEWAY"),
        ("OUTLET OF PRIEST LAKE", "OUTLET OF"),
    ],
)
def test_each_regulated_pattern_matches(name, needle):
    h = regulation_hint(name, 5000.0)
    assert h.level == REGULATED
    assert needle in h.reason.upper()


def test_outlet_of_reservoir_pattern_level_only():
    assert regulation_hint("OUTLET OF ROCK CREEK RESERVOIR", 5000).level == REGULATED


def test_at_something_dam_pattern():
    assert regulation_hint("COLUMBIA RIVER AT GRAND COULEE DAM", 74000).level == REGULATED


def test_non_regulated_names_with_large_area_are_unknown():
    for name in ["CLEARWATER RIVER AT OROFINO ID", "SALMON RIVER AT WHITE BIRD", "FLATHEAD RIVER NR POLSON"]:
        assert regulation_hint(name, 5000).level == UNKNOWN


# --------------------------------------------------------------------------- #
# Case-insensitivity and word boundaries
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("name", ["snake river below hells canyon", "Snake River Below Hells Canyon", "SNAKE RIVER BELOW HELLS CANYON"])
def test_case_insensitive(name):
    assert regulation_hint(name, 5000).level == REGULATED


def test_lowercase_dam_and_mixed_case_canal():
    assert regulation_hint("big dam site", 5000).level == REGULATED
    assert regulation_hint("Main Canal", 5000).level == REGULATED


@pytest.mark.parametrize(
    "name",
    [
        "DAMSON CR NR TOWN",   # DAM inside a longer word
        "ADAM CR NR TOWN",     # DAM at the end of a word
        "MADAME CR",
        "BELOWE CR NR TOWN",   # BELOW + extra letter
        "BLACKFOOT RIVER NR BONNER",  # BL prefix of a word
        "BLUE RIVER AT BLUE RIVER",
        "CANALE CR",
        "RESERVOIRX CR",
        "FLUMEN CR",
    ],
)
def test_word_boundary_prevents_substring_matches(name):
    assert regulation_hint(name, 5000).level == UNKNOWN


def test_word_boundary_does_not_block_punctuation_neighbours():
    assert regulation_hint("SNAKE R, BELOW, DAM", 5000).level == REGULATED
    assert regulation_hint("N FK (DAM)", 5000).level == REGULATED


def test_substring_name_with_small_area_falls_through_to_area_rule():
    assert regulation_hint("DAMSON CR NR TOWN", 50).level == UNREGULATED


# --------------------------------------------------------------------------- #
# Precedence
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("area", [0.5, 10, 199.9])
def test_regulated_name_beats_small_area(area):
    assert regulation_hint("LITTLE CR BELOW DAM", area).level == REGULATED


# --------------------------------------------------------------------------- #
# Area thresholds
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("area", [0.001, 1, 50, 199, 199.9, 199.999])
def test_small_area_unregulated(area):
    assert regulation_hint("PLAIN CR NR TOWN", area).level == UNREGULATED


@pytest.mark.parametrize("area", [200, 200.0, 200.1, 1000, 1e6])
def test_area_at_or_above_200_unknown(area):
    assert regulation_hint("PLAIN CR NR TOWN", area).level == UNKNOWN


@pytest.mark.parametrize("area", [0, 0.0, -1, -199.0, math.nan, math.inf, -math.inf, None, "abc", object()])
def test_invalid_area_unknown(area):
    assert regulation_hint("PLAIN CR NR TOWN", area).level == UNKNOWN


def test_numpy_scalars_accepted():
    np = pytest.importorskip("numpy")
    assert regulation_hint("PLAIN CR", np.float64(50.0)).level == UNREGULATED
    assert regulation_hint("PLAIN CR", np.float64(500.0)).level == UNKNOWN
    assert regulation_hint("PLAIN CR", np.float64("nan")).level == UNKNOWN


def test_int_area_accepted():
    assert regulation_hint("PLAIN CR", 100).level == UNREGULATED


# --------------------------------------------------------------------------- #
# None / empty names
# --------------------------------------------------------------------------- #
def test_none_name_uses_area_rule():
    assert regulation_hint(None, 50).level == UNREGULATED
    assert regulation_hint(None, 500).level == UNKNOWN
    assert regulation_hint(None, None).level == UNKNOWN


def test_empty_name_uses_area_rule():
    assert regulation_hint("", 50).level == UNREGULATED
    assert regulation_hint("", None).level == UNKNOWN


# --------------------------------------------------------------------------- #
# Reason text
# --------------------------------------------------------------------------- #
CASES = [
    ("SNAKE RIVER BELOW X", 5000),
    ("PLAIN CR", 50),
    ("PLAIN CR", 5000),
    (None, None),
    ("PLAIN CR", float("nan")),
]


@pytest.mark.parametrize("name, area", CASES)
def test_reason_always_says_heuristic_not_verified(name, area):
    r = regulation_hint(name, area).reason.lower()
    assert "heuristic" in r
    assert "verified" in r  # "not verified"


def test_reason_names_the_matched_pattern():
    assert "BELOW" in regulation_hint("SNAKE RIVER BELOW X", 5000).reason.upper()
    assert "CANAL" in regulation_hint("MAIN CANAL", 5000).reason.upper()
    assert "WASTEWAY" in regulation_hint("MILNER WASTEWAY", 5000).reason.upper()


def test_different_patterns_give_different_reasons():
    assert regulation_hint("A BELOW B", 5000).reason != regulation_hint("A CANAL B", 5000).reason


def test_reason_is_pure_function_of_inputs():
    assert regulation_hint("A BELOW B", 10) == regulation_hint("A BELOW B", 10)
