"""Bundle search under budget x calorie caps."""
from dataclasses import dataclass
from itertools import combinations

from mcdcalc.nutrition import CONF_RANK, combo_nutrition, mod_delta

MAIN_CATEGORIES = {"鸡肉汉堡/卷", "巨无霸牛鱼肉堡", "安格斯MAX厚牛堡", "炸鸡", "蘸酱炸鸡"}
DRINK_CATEGORIES = {"饮品", "麦咖啡™"}
LIGHT_MIN_KCAL = 10
BUDGETS = range(1000, 8001, 100)
KCAL_CAPS = range(200, 1501, 10)


@dataclass
class Option:
    code: str
    name: str
    variant: str
    removed: tuple
    removed_names: tuple
    price_fen: int
    gold: dict | None
    kcal: float
    low: float
    high: float
    protein: float
    confidence: str
    is_main: bool
    is_drink: bool
    is_combo: bool


@dataclass
class Bundle:
    options: tuple
    price_fen: int
    kcal: float
    low: float
    high: float
    protein: float
    confidence: str
    best_fen: int
    needs_gold: bool
    gold_fen: int | None
    gold_fee_fen: int


def _parts(p):
    if not p["isCombo"]:
        return [p]
    return [next((c for c in r["choices"] if c["isDefault"]), None) for r in p["rounds"]]


def _heavy(code, mods):
    return [m for m in mods if (mod_delta(code, m["code"])["kcal"] or 0) >= LIGHT_MIN_KCAL]


def build_options(products):
    out = []
    for p in products:
        parts = _parts(p)
        if p.get("priceFen") is None or None in parts:
            continue
        cats = set(p["categories"])
        is_main = p["isCombo"] or bool(cats & MAIN_CATEGORIES)
        is_drink = not p["isCombo"] and bool(cats & DRINK_CATEGORIES)
        heavy = [_heavy(x["code"], x.get("mods", [])) for x in parts]
        variants = [("standard", [[] for _ in parts])] + ([("light", heavy)] if any(heavy) else [])
        for variant, removed in variants:
            t = combo_nutrition([{"code": x["code"], "name": x["name"], "removed": [m["code"] for m in r]}
                                 for x, r in zip(parts, removed)])
            if t.missing:
                break
            out.append(Option(
                p["code"], p["name"], variant,
                tuple((x["code"], m["code"]) for x, r in zip(parts, removed) for m in r),
                tuple(m["name"] for r in removed for m in r),
                p["priceFen"], p.get("gold"), t.kcal, t.low, t.high, t.protein, t.confidence, is_main, is_drink,
                p["isCombo"]))
    return out


def _bundle(opts) -> Bundle:
    price = sum(o.price_fen for o in opts)
    golds = [o.gold for o in opts if o.gold]
    fee = max((g["feeFen"] for g in golds), default=0)
    gold = sum(o.gold["priceFen"] if o.gold else o.price_fen for o in opts) + fee if golds else None
    best = min(price, gold) if gold is not None else price
    return Bundle(opts, price, sum(o.kcal for o in opts), sum(o.low for o in opts), sum(o.high for o in opts),
                  sum(o.protein for o in opts), min((o.confidence for o in opts), key=CONF_RANK.get),
                  best, gold is not None and gold < price, gold, fee)


def build_bundles(options, max_items=3):
    out = []
    for k in range(1, max_items + 1):
        for combo in combinations(options, k):
            if len({o.code for o in combo}) < k:
                continue
            mains = sum(o.is_main for o in combo)
            combos = sum(o.is_combo for o in combo)
            if not 1 <= mains <= 2 or sum(o.is_drink for o in combo) > 1 or combos > 1 or (combos and k > 2):
                continue
            out.append(_bundle(combo))
    return out


def _cheaper(a, b):
    return b is None or (a.best_fen, a.kcal) < (b.best_fen, b.kcal)


def _lighter(a, b):
    return b is None or (a.kcal, a.best_fen) < (b.kcal, b.best_fen)


def _stronger(a, b):
    return b is None or (a.protein, -a.best_fen, -a.kcal) > (b.protein, -b.best_fen, -b.kcal)


def pick(bundles, budget_fen, kcal_cap):
    best = {"cheapest": None, "lightest": None, "protein": None}
    for b in bundles:
        if b.best_fen <= budget_fen and b.kcal <= kcal_cap:
            _update(best, b)
    return best if best["cheapest"] else {}


def _update(best, b):
    if _cheaper(b, best["cheapest"]):
        best["cheapest"] = b
    if _lighter(b, best["lightest"]):
        best["lightest"] = b
    if _stronger(b, best["protein"]):
        best["protein"] = b


def recommend_grid(bundles, budgets=BUDGETS, caps=KCAL_CAPS):
    by_price = sorted(bundles, key=lambda b: b.best_fen)
    grid = {}
    for cap in caps:
        pool = [b for b in by_price if b.kcal <= cap]
        best = {"cheapest": None, "lightest": None, "protein": None}
        i = 0
        for budget in budgets:
            while i < len(pool) and pool[i].best_fen <= budget:
                _update(best, pool[i])
                i += 1
            grid[(budget, cap)] = dict(best) if best["cheapest"] else {}
    return grid
