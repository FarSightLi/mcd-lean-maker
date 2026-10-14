"""Precompute everything the static demo page needs into web/data."""
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

from mcdcalc.nutrition import item_nutrition, mod_delta
from mcdcalc.offers import quote
from mcdcalc.recommend import BUDGETS, KCAL_CAPS, build_bundles, build_options, recommend_grid

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "web" / "snapshot"
MAX_BYTES = 3_000_000
RESULT_KEYS = ("kcal", "low", "high", "protein", "fat", "carbohydrate", "sodium", "confidence", "adjusted")


def _mod_info(code, m):
    d = mod_delta(code, m["code"])
    return {"code": m["code"], "name": m["name"], "kcal": d["kcal"], "range": d["range"], "confidence": d["confidence"]}


def _results(code, name, mods):
    if item_nutrition(code, name) is None:
        return None
    out = {}
    for mask in range(2 ** len(mods)):
        removed = [m["code"] for i, m in enumerate(mods) if mask >> i & 1]
        n = asdict(item_nutrition(code, name, removed))
        out[str(mask)] = {k: n[k] for k in RESULT_KEYS}
    return out


def build_items(products):
    items = {}

    def add(code, name, mods, extra):
        if code not in items:
            items[code] = {"name": name, "mods": [_mod_info(code, m) for m in mods],
                           "results": _results(code, name, mods), **extra}

    for p in products:
        add(p["code"], p["name"], p["mods"], {
            "image": p.get("image"), "categories": p["categories"], "isNew": p["isNew"], "isCombo": p["isCombo"],
            "priceFen": p["priceFen"], "originalFen": p["originalFen"], "gold": p["gold"],
            "rounds": [{"name": r["name"], "choices": [{"code": c["code"], "isDefault": c["isDefault"],
                                                        "diffFen": c["diffFen"]} for c in r["choices"]]}
                       for r in p["rounds"]]})
        for r in p["rounds"]:
            for c in r["choices"]:
                add(c["code"], c["name"], c["mods"], {"choiceOnly": True})
    return items


def _bundle_json(b):
    q = quote([{"priceFen": o.price_fen, "originalFen": o.price_fen, "qty": 1, "gold": o.gold} for o in b.options])
    return {"items": [{"code": o.code, "name": o.name, "variant": o.variant, "removed": list(o.removed_names)}
                      for o in b.options],
            "priceFen": b.price_fen, "gold": {"goldFen": q.gold_fen, "verdict": q.verdict} if q.gold_fen else None,
            "kcal": b.kcal, "low": b.low, "high": b.high, "protein": b.protein, "confidence": b.confidence,
            "bestFen": b.best_fen, "needsGold": b.needs_gold, "goldFeeFen": b.gold_fee_fen}


def build_recommend(products):
    grid = recommend_grid(build_bundles(build_options(products)))
    bundles, index = [], {}
    out = {}
    for (budget, cap), plans in grid.items():
        idxs = []
        for key in ("cheapest", "lightest", "protein"):
            b = plans.get(key)
            if b is None:
                continue
            ident = id(b)
            if ident not in index:
                index[ident] = len(bundles)
                bundles.append(_bundle_json(b))
            idxs.append(index[ident])
        out[f"{budget}_{cap}"] = idxs
    return {"budgets": list(BUDGETS), "caps": list(KCAL_CAPS), "bundles": bundles, "grid": out}


LEAN_CATEGORY = "500大卡套餐"


def build_categories(tree, items):
    """Ordered categories for the menu UI; the official 500 kcal category is pinned first."""
    out = []
    for c in tree or []:
        name = c["name"].replace("\n", "")
        kept = [i for i in c["items"] if i["code"] in items and not items[i["code"]].get("choiceOnly")]
        if kept:
            out.append({"name": name, "label": c["name"], "lean": name == LEAN_CATEGORY, "items": kept})
    return sorted(out, key=lambda c: not c["lean"])


def build_payload(products: list, meta: dict) -> dict[str, object]:
    meta = dict(meta)
    tree = meta.pop("categories", None)
    items = build_items(products)
    meta.update({"builtAt": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M"),
                 "budgets": [BUDGETS.start, BUDGETS.stop - 1, BUDGETS.step],
                 "caps": [KCAL_CAPS.start, KCAL_CAPS.stop - 1, KCAL_CAPS.step],
                 "confidenceNote": "官方=营养表原值;高/中/低=特制项或新品估算"})
    return {"items.json": items, "categories.json": build_categories(tree, items), "recommend.json": build_recommend(products), "meta.json": meta}


def build(out_dir: Path) -> dict:
    products = json.loads((SNAP / "products.json").read_text(encoding="utf-8"))
    meta = json.loads((SNAP / "meta.json").read_text(encoding="utf-8"))
    out_dir.mkdir(parents=True, exist_ok=True)
    files = build_payload(products, meta)
    sizes = {}
    for name, obj in files.items():
        data = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
        (out_dir / name).write_text(data, encoding="utf-8")
        sizes[name] = len(data.encode())
    if sum(sizes.values()) > MAX_BYTES:
        raise SystemExit(f"web/data 超出 {MAX_BYTES} 字节: {sizes}")
    return sizes


if __name__ == "__main__":
    print(build(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "web" / "data"))
