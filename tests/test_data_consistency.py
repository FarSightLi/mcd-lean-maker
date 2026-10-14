import json
from pathlib import Path

from mcdcalc.data import load

FIX = Path(__file__).parent / "fixtures" / "modification-options.raw.json"


def test_every_collected_option_has_calories():
    collected = set(json.loads(FIX.read_text(encoding="utf-8"))["options"])
    table = load("modification-calories.json")["options"]
    assert collected == set(table)


def test_option_schema():
    for code, o in load("modification-calories.json")["options"].items():
        lo, hi = o["range"]
        assert lo <= o["kcal"] <= hi, code
        assert o["method"] in {"A", "B", "C"} and o["confidence"] in {"高", "中", "低"}, code


def test_derived_schema():
    for name, d in load("derived-nutrition.json").items():
        lo, hi = d["range"]
        assert lo <= d["energyKcal"] <= hi and d["derivation"], name
