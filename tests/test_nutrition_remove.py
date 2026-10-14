from mcdcalc.nutrition import item_nutrition, mod_delta


def test_bigmac_remove_sauce_and_cheese():
    n = item_nutrition("1100", "巨无霸", ["100116", "100141"])
    assert n.kcal == 513 - 90 - 46 == 377
    assert (n.low, n.high) == (513 - 112 - 50, 513 - 70 - 44) == (351, 399)
    assert n.confidence == "中"           # 巨无霸酱为中
    assert n.adjusted is False            # 巨无霸酱无 nutrients
    assert n.protein == 27 - 3            # 吉士 nutrients 已扣


def test_override_double_cheese_two_slices():
    assert mod_delta("1120", "100141")["kcal"] == 92
    assert mod_delta("1100", "100141")["kcal"] == 46


def test_vegetables_keep_adjusted_true():
    n = item_nutrition("1100", "巨无霸", ["100168", "100202", "100212"])
    assert n.kcal == 513 - 5 and n.adjusted is True and n.confidence == "高"


def test_non_caloric_option_is_zero():
    assert mod_delta("3050", "200002")["kcal"] == 0


def test_unmatched_product_returns_none():
    assert item_nutrition("x", "不存在的堡", ["100141"]) is None


def test_unknown_mod_goes_to_missing_not_crash():
    from mcdcalc.nutrition import combo_nutrition
    assert mod_delta("1100", "999999")["kcal"] is None
    t = combo_nutrition([{"code": "1100", "name": "巨无霸", "removed": ["100116", "999999"]}])
    assert t.kcal == 513 - 90 and t.missing == ["巨无霸·特制999999"]


def test_full_fields_official_and_estimated():
    base = item_nutrition("1100", "巨无霸")
    assert base.kj > 0 and base.calcium is not None and base.estimated == ()
    n = item_nutrition("1100", "巨无霸", ["100116", "100141"])
    assert round(n.kj, 1) == round(base.kj - (90 + 46) * 4.184, 1)      # kJ 随 kcal 差值换算
    assert n.calcium == base.calcium - 83                                # 吉士有钙数据,巨无霸酱没有
    assert {"kj", "calcium", "protein"} <= set(n.estimated)


def test_calcium_kept_and_marked_when_mod_has_no_data():
    base = item_nutrition("1100", "巨无霸")
    n = item_nutrition("1100", "巨无霸", ["100116"])
    assert n.calcium == base.calcium and "calcium" in n.estimated


def test_total_sums_kj_calcium_and_description():
    from mcdcalc.nutrition import combo_nutrition, match
    t = combo_nutrition([{"code": "1100", "name": "巨无霸"}, {"code": "4810", "name": "中薯条"}])
    a, b = match("1100", "巨无霸"), match("4810", "中薯条")
    assert t.kj == a.kj + b.kj and t.calcium == a.calcium + b.calcium
    assert match(None, "纯悦").description == "能量约清水1杯"
