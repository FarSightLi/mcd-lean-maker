"""Rule-based meal bundles for the static demo page (build side only)."""
from dataclasses import dataclass
from itertools import combinations

from mcdcalc.nutrition import CONF_RANK, combo_nutrition, mod_delta

DRINK_CATEGORIES = {"饮品", "麦咖啡™"}
# Roles come from product names, not menu categories: marketing categories (人气热卖, 500大卡套餐)
# and choice-only "combos" (可乐/派/新地 with a flavour round) say nothing about what the item is.
MAIN_WORDS = ("堡", "卷", "巨无霸", "麦香鸡", "麦香鱼", "麦满分", "鸡排", "脆汁鸡", "猪柳", "主食")
DESSERT_WORDS = ("冰淇淋", "圆筒", "新地", "麦旋风", "派", "雪冰", "阿芙佳朵")
DRINK_WORDS = ("可乐", "雪碧", "芬达", "茶", "咖啡", "奶", "汁", "饮", "怡泉", "纯悦", "麦炫酷", "美式", "拿铁", "黑巧")
SIDE_WORDS = ("薯", "麦乐鸡", "鸡翅", "V翅", "玉米", "苹果片", "芝士条", "鸡块", "小食")
SKIP_WORDS = ("双人", "多人", "分享", "拼", "7件", "八件", "小食盘", "耳机", "挠")
SAUCE_WORD = "酱"
MAIN, SIDE, DRINK, DESSERT, MEAL = "main", "side", "drink", "dessert", "meal"
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
    role: str
    fat: float = 0
    carbohydrate: float = 0
    sodium: float = 0
    kj: float = 0
    calcium: float | None = None
    estimated: tuple = ()


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
    fat: float = 0
    carbohydrate: float = 0
    sodium: float = 0
    kj: float = 0
    calcium: float | None = None
    estimated: tuple = ()


def _parts(p):
    if not p["isCombo"]:
        return [p]
    return [next((c for c in r["choices"] if c["isDefault"]), None) for r in p["rounds"]]


def _heavy(code, mods):
    return [m for m in mods if (mod_delta(code, m["code"])["kcal"] or 0) >= LIGHT_MIN_KCAL]


def item_role(name: str, categories=()) -> str | None:
    """main/side/drink/dessert for a single item; None for sauces, merch and unknowns."""
    if any(w in name for w in DESSERT_WORDS):
        return DESSERT
    if any(w in name for w in MAIN_WORDS):
        return MAIN
    if set(categories) & DRINK_CATEGORIES or any(w in name for w in DRINK_WORDS):
        return DRINK
    if any(w in name for w in SIDE_WORDS) or "炸鸡" in categories:
        return SIDE
    return None


def product_role(p, parts) -> str | None:
    """A real 套餐 has food plus a drink round; other combos take the role of their parts."""
    if any(w in p["name"] for w in SKIP_WORDS) and "套餐" not in p["name"]:
        return None
    if not p["isCombo"]:
        if SAUCE_WORD in p["name"]:
            return None
        return item_role(p["name"], p["categories"])
    roles = [item_role(x["name"]) for x in parts]
    if DRINK in roles and (MAIN in roles or SIDE in roles):
        return MEAL
    for r in (MAIN, DRINK, DESSERT, SIDE):
        if r in roles:
            return r
    return None


def valid_meal(roles) -> bool:
    """One 套餐 (+ at most one drink/side/dessert), or 1-2 mains + at least one side/drink.

    Desserts are add-ons only; at most one drink.
    """
    if roles.count(DRINK) > 1:
        return False
    if MEAL in roles:
        return roles.count(MEAL) == 1 and len(roles) <= 2 and MAIN not in roles
    return 1 <= roles.count(MAIN) <= 2 and (SIDE in roles or DRINK in roles)


def build_options(products):
    out = []
    for p in products:
        parts = _parts(p)
        if p.get("priceFen") is None or None in parts:
            continue
        role = product_role(p, parts)
        if role is None:
            continue
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
                p["priceFen"], p.get("gold"), t.kcal, t.low, t.high, t.protein, t.confidence, role,
                t.fat, t.carbohydrate, t.sodium, t.kj, t.calcium, tuple(t.estimated)))
    return out


def _bundle(opts) -> Bundle:
    price = sum(o.price_fen for o in opts)
    golds = [o.gold for o in opts if o.gold]
    fee = max((g["feeFen"] for g in golds), default=0)
    gold = sum(o.gold["priceFen"] if o.gold else o.price_fen for o in opts) + fee if golds else None
    best = min(price, gold) if gold is not None else price
    return Bundle(opts, price, sum(o.kcal for o in opts), sum(o.low for o in opts), sum(o.high for o in opts),
                  sum(o.protein for o in opts), min((o.confidence for o in opts), key=CONF_RANK.get),
                  best, gold is not None and gold < price, gold, fee,
                  sum(o.fat for o in opts), sum(o.carbohydrate for o in opts), sum(o.sodium for o in opts),
                  sum(o.kj for o in opts),
                  None if any(o.calcium is None for o in opts) else sum(o.calcium for o in opts),
                  tuple(dict.fromkeys(k for o in opts for k in o.estimated)))


def build_bundles(options, max_items=3):
    out = []
    for k in range(1, max_items + 1):
        for combo in combinations(options, k):
            if len({o.code for o in combo}) < k:
                continue
            if not valid_meal([o.role for o in combo]):
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
