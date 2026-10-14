"""Bundled data loading and name normalization."""
import json
import unicodedata
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
NUTRITION_FIELDS = ("energyKj", "energyKcal", "protein", "fat", "carbohydrate", "sodium", "calcium")


def normalize(name: str) -> str:
    return unicodedata.normalize("NFKC", name).replace(" ", "").strip()


@lru_cache(maxsize=None)
def load(name: str):
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def parse_nutrition_text(text: str) -> list[dict]:
    """Parse the `data` text of list-nutrition-foods; keeps the first row per name."""
    rows, seen = [], set()
    for line in text.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        name, desc, *nums = line.rsplit(",", len(NUTRITION_FIELDS) + 1)
        if name in seen:
            continue
        seen.add(name)
        row = {"name": name, "description": None if desc == "null" else desc}
        row.update({k: float(v) for k, v in zip(NUTRITION_FIELDS, nums)})
        rows.append(row)
    return rows


@lru_cache(maxsize=None)
def nutrition_index() -> dict:
    return {normalize(r["name"]): r for r in load("nutrition.json")}
