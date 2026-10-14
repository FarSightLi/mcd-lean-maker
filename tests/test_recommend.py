from mcdcalc.recommend import BUDGETS, KCAL_CAPS, build_bundles, build_options, pick, recommend_grid


def P(code, name, cat, price, mods=(), combo=False, rounds=None):
    return {"code": code, "name": name, "categories": [cat], "tags": [], "isCombo": combo,
            "priceFen": price, "originalFen": price, "gold": None,
            "mods": [{"code": c, "name": n} for c, n in mods], "rounds": rounds or []}


BIGMAC = P("1100", "巨无霸", "巨无霸牛鱼肉堡", 2550,
           [("100116", "巨无霸酱"), ("100141", "吉士"), ("100168", "生菜")])
HAMBURGER = P("1000", "汉堡包", "巨无霸牛鱼肉堡", 1200)
FRIES = P("4810", "中薯条", "小食甜品/其他", 1250)
COLA = P("3050", "可乐中杯", "饮品", 1000)
SPRITE = P("3060", "雪碧中杯", "饮品", 1000)
MERCH = P("9", "“葱不求人“按摩捶痒痒挠", "小食甜品/其他", 1990)
PRODUCTS = [BIGMAC, HAMBURGER, FRIES, COLA, SPRITE, MERCH]


def test_options_standard_and_light():
    opts = {(o.code, o.variant): o for o in build_options(PRODUCTS)}
    assert opts[("1100", "light")].kcal == 377
    assert opts[("1100", "light")].removed_names == ("巨无霸酱", "吉士")   # 生菜 < 10 kcal 不去
    assert ("4810", "light") not in opts
    assert not any(code == "9" for code, _ in opts)                      # 无营养数据的周边


def test_combo_uses_default_choices():
    combo = P("99", "巨无霸套餐", "巨无霸牛鱼肉堡", 3800, combo=True, rounds=[
        {"name": "主食", "choices": [{"code": "1100", "name": "巨无霸", "isDefault": True, "diffFen": 0,
                                    "mods": [{"code": "100116", "name": "巨无霸酱"}]}]},
        {"name": "饮料", "choices": [{"code": "3050", "name": "可乐中杯", "isDefault": True, "diffFen": 0, "mods": []},
                                   {"code": "3060", "name": "雪碧中杯", "isDefault": False, "diffFen": 0, "mods": []}]},
    ])
    opts = {o.variant: o for o in build_options([combo])}
    assert opts["standard"].kcal == 513 + 147 and opts["light"].kcal == 513 - 90 + 147
    assert opts["standard"].is_main and not opts["standard"].is_drink


def test_bundle_rules():
    bundles = build_bundles(build_options(PRODUCTS))
    for b in bundles:
        assert 1 <= sum(o.is_main for o in b.options) <= 2
        assert sum(o.is_drink for o in b.options) <= 1
        assert len({o.code for o in b.options}) == len(b.options)
        assert sum(o.is_combo for o in b.options) <= 1


def test_pick_three_plans():
    plans = pick(build_bundles(build_options(PRODUCTS)), 3000, 400)
    assert [o.code for o in plans["cheapest"].options] == ["1000"]
    assert [o.code for o in plans["lightest"].options] == ["1000"]
    best = plans["protein"].options
    assert [(o.code, o.variant) for o in best] == [("1100", "light")]
    assert pick([], 3000, 400) == {}


def test_grid_matches_pick_everywhere():
    bundles = build_bundles(build_options(PRODUCTS))
    grid = recommend_grid(bundles)
    assert len(grid) == len(BUDGETS) * len(KCAL_CAPS) == 71 * 131
    for (budget, cap), plans in grid.items():
        expect = pick(bundles, budget, cap)
        assert {k: v.best_fen for k, v in plans.items()} == {k: v.best_fen for k, v in expect.items()}
        assert {k: v.kcal for k, v in plans.items()} == {k: v.kcal for k, v in expect.items()}


def test_gold_card_net_price_used_for_ranking():
    bigmac = {**BIGMAC, "gold": {"priceFen": 500, "feeFen": 1900}}
    cola = {**COLA, "gold": {"priceFen": 500, "feeFen": 1900}}
    bundles = build_bundles(build_options([bigmac, HAMBURGER, FRIES, cola]))
    solo = next(b for b in bundles if [(o.code, o.variant) for o in b.options] == [("1100", "standard")])
    assert (solo.price_fen, solo.gold_fen, solo.best_fen, solo.needs_gold) == (2550, 2400, 2400, True)
    pair = next(b for b in bundles if {o.code for o in b.options} == {"1100", "3050"} and all(o.variant == "standard" for o in b.options))
    assert pair.gold_fen == 500 + 500 + 1900 and pair.gold_fee_fen == 1900   # 卡费一单一次
    plans = pick(bundles, 2450, 600)
    assert plans["protein"].best_fen <= 2450 and plans["protein"].needs_gold


def test_no_gold_bundle_fields():
    b = build_bundles(build_options([HAMBURGER]))[0]
    assert (b.gold_fen, b.gold_fee_fen, b.best_fen, b.needs_gold) == (None, 0, 1200, False)
