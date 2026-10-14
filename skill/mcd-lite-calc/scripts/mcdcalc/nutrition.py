"""Nutrition matching, modification removal and summing."""
from dataclasses import dataclass, replace

from mcdcalc.data import load, normalize, nutrition_index

CONF_RANK = {"官方": 3, "高": 2, "中": 1, "低": 0}


@dataclass(frozen=True)
class Nutrition:
    kcal: float
    low: float
    high: float
    protein: float
    fat: float
    carbohydrate: float
    sodium: float
    confidence: str
    source: str
    adjusted: bool = True


def _from_row(row: dict, source: str) -> Nutrition:
    kcal = row["energyKcal"]
    return Nutrition(
        kcal, kcal, kcal,
        row["protein"], row["fat"], row["carbohydrate"], row["sodium"],
        "官方", source,
    )


def _lookup(table: dict, code: str | None, name: str):
    if code and code in table:
        return table[code]
    norm_table = {normalize(k): v for k, v in table.items()}
    return norm_table.get(normalize(name))


def match(code: str | None, name: str) -> Nutrition | None:
    idx = nutrition_index()

    alias = _lookup(load("aliases.json"), code, name)
    if alias and normalize(alias) in idx:
        return _from_row(idx[normalize(alias)], "alias")

    if normalize(name) in idx:
        return _from_row(idx[normalize(name)], "exact")

    derived = _lookup(load("derived-nutrition.json"), code, name)
    if derived:
        lo, hi = derived["range"]
        return Nutrition(
            derived["energyKcal"], lo, hi,
            derived["protein"], derived["fat"], derived["carbohydrate"], derived["sodium"],
            derived["confidence"], "derived",
        )

    return None


NUTRIENT_KEYS = ("protein", "fat", "carbohydrate", "sodium")


def mod_delta(product_code: str, mod_code: str) -> dict:
    table = load("modification-calories.json")
    if mod_code in table.get("nonCaloric", {}):
        return {"name": "", "kcal": 0, "range": [0, 0], "confidence": "高"}
    base = table["options"][mod_code]
    override = table.get("overrides", {}).get(product_code, {}).get(mod_code)
    return {**base, **override} if override else base


def remove_mods(base: Nutrition, product_code: str, removed) -> Nutrition:
    n = base
    for code in removed:
        d = mod_delta(product_code, code)
        lo, hi = d["range"]
        nutrients = d.get("nutrients")
        changes = {"kcal": n.kcal - d["kcal"], "low": n.low - hi, "high": n.high - lo}
        if nutrients:
            changes.update({k: getattr(n, k) - nutrients.get(k, 0) for k in NUTRIENT_KEYS})
        elif d["kcal"] >= 10:
            # tiny items (lettuce, onion) do not meaningfully move macros
            changes["adjusted"] = False
        if CONF_RANK[d["confidence"]] < CONF_RANK[n.confidence]:
            changes["confidence"] = d["confidence"]
        n = replace(n, **changes)
    return n


def item_nutrition(code: str, name: str, removed=()) -> Nutrition | None:
    base = match(code, name)
    return remove_mods(base, code, removed) if base else None
