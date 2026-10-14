"""Nutrition matching, modification removal and summing."""
from dataclasses import dataclass

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
