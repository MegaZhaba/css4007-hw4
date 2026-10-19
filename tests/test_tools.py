import json
import time

import pytest

from tools import calculate, lookup, run_tool, tool_definitions


# ---------------------------------------------------------------- lookup

def test_lookup_finds_2025_population():
    r = lookup("Ossbridge", "population_2025")
    assert r["value"] == 52904
    assert r["source"] == "NR-01"
    assert "52,904" in r["evidence"]


def test_lookup_all_three_profile_templates():
    # The three profile templates phrase population differently.
    assert lookup("Ossford", "population_2025")["value"] == 30982
    assert lookup("Tarnvale", "population_2025")["value"] == 71388
    assert lookup("Kelmarsh", "population_2025")["value"] == 24117


def test_lookup_misspelled_name_suggests_and_does_not_guess():
    r = lookup("Ossbrige", "area_km2")
    assert "error" in r and "value" not in r
    assert "Ossbridge" in r["error"] and "Ossford" in r["error"]


def test_lookup_similar_names_are_different_districts():
    a = lookup("Ossbridge", "area_km2")
    b = lookup("Ossford", "area_km2")
    assert (a["value"], a["source"]) == (1284.6, "NR-01")
    assert (b["value"], b["source"]) == (846.2, "NR-02")


@pytest.mark.parametrize("district, field, current, archived_value", [
    ("Tarnvale", "schools", 29, 27),
    ("Tarnvale", "pupils_2025_26", 10652, 9870),
    ("Kelmarsh", "pupils_2025_26", 3268, 2944),
    ("Kelmarsh", "water_use_2025_megalitres", 1739, 1652),
])
def test_lookup_ignores_archived_profiles(district, field, current, archived_value):
    r = lookup(district, field)
    assert r["value"] == current != archived_value
    assert r["source"] not in ("NR-13", "NR-14")
    assert "archived" in r["note"]


def test_lookup_applies_correction_notice():
    r = lookup("Brightwater", "area_km2")
    assert r["value"] == 921.4
    assert r["source"] == "NR-16"
    # other Brightwater figures still come from the profile
    assert lookup("Brightwater", "population_2025")["source"] == "NR-05"


def test_lookup_converts_cubic_metres_to_megalitres():
    r = lookup("Lindenmoor", "water_use_2025_megalitres")
    assert r["value"] == pytest.approx(2151.4)
    assert r["unit"] == "ML"
    assert "cubic metres" in r["note"]


def test_lookup_region_tariff():
    assert lookup("Region", "water_tariff_2025_tenge_per_m3")["value"] == 142.35
    assert "error" in lookup("Millbrook", "water_tariff_2025_tenge_per_m3")


@pytest.mark.parametrize("district, field", [
    ("Atlantis", "area_km2"), ("", "area_km2"), (None, "area_km2"), (42, "area_km2"),
    ("x" * 10_000, "area_km2"), ("Redfen", "density"), ("Redfen", None),
    ("../../.env", "area_km2"),
])
def test_lookup_never_crashes(district, field):
    r = lookup(district, field)
    assert set(r) == {"error"}


def test_lookup_result_is_short():
    for field in ("population_2025", "area_km2", "budget_2025_million_tenge"):
        assert len(json.dumps(lookup("Harrowfield", field))) < 600


# ---------------------------------------------------------------- calculate

def test_calculate_multiplication():
    assert calculate("48317 * 1.0947")["result"] == pytest.approx(52892.6199)


def test_calculate_precedence_and_parentheses():
    assert calculate("(52904 - 48317) / 48317 * 100")["result"] == pytest.approx(9.4935, abs=1e-4)
    assert calculate("-2 ** 2")["result"] == -4
    assert calculate("37203 / 758.6 - 44675 / 921.4")["result"] == pytest.approx(0.55566, abs=1e-5)


@pytest.mark.parametrize("expr", [
    "__import__('os').system('echo hi')",
    "(1).__class__",
    "9**9**9",
    "().__class__.__bases__[0].__subclasses__()",
    "open('.env').read()",
    "lambda: 1",
    "'a' * 10",
    "[1, 2]",
    "x + 1",
])
def test_calculate_refuses_dangerous_input_quickly(expr):
    start = time.perf_counter()
    r = calculate(expr)
    assert set(r) == {"error"}
    assert time.perf_counter() - start < 0.5


def test_calculate_division_by_zero():
    assert calculate("1 / 0") == {"error": "division by zero"}
    assert calculate("0 ** -1") == {"error": "division by zero"}


def test_calculate_huge_numbers_refused():
    assert "too large" in calculate("10 ** 400")["error"]
    assert "too large" in calculate("1e300 * 1e300")["error"]
    assert "too large" in calculate("99999999 * 99999999 * 99999999")["error"]


def test_calculate_bad_syntax_and_length():
    assert "commas" in calculate("44,675 / 921.4")["error"]
    assert "parse" in calculate("2 +")["error"]
    assert "characters" in calculate("1+" * 200 + "1")["error"]
    assert "characters" in calculate("")["error"]
    assert "characters" in calculate(None)["error"]


# ---------------------------------------------------------------- dispatch

def test_run_tool_validates_json_string_arguments():
    assert run_tool("lookup", '{"district": "Redfen", "field": "schools"}')["value"] == 10
    assert "valid JSON" in run_tool("lookup", "{district: Redfen}")["error"]
    assert "missing" in run_tool("lookup", '{"district": "Redfen"}')["error"]
    assert "unexpected" in run_tool("calculate", '{"expression": "1", "x": 2}')["error"]
    assert "unknown tool" in run_tool("shell", '{"cmd": "ls"}')["error"]
    assert "object" in run_tool("calculate", '["1+1"]')["error"]


def test_tool_definitions_shape():
    for vague in (False, True):
        defs = tool_definitions(vague=vague)
        assert [d["function"]["name"] for d in defs] == ["lookup", "calculate"]
    assert tool_definitions(vague=True)[0]["function"]["description"] == "Looks things up."
    # C1 changes only the description, nothing else
    a, b = tool_definitions(False)[0]["function"], tool_definitions(True)[0]["function"]
    assert a["parameters"] == b["parameters"]
