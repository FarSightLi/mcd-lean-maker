from mcdcalc.nutrition import combo_nutrition, item_nutrition, sum_nutrition


def test_combo_sums_parts():
    t = combo_nutrition([
        {"code": "1100", "name": "巨无霸", "removed": ["100116"]},
        {"code": "4810", "name": "中薯条", "removed": []},
        {"code": "3050", "name": "可乐中杯", "removed": ["200002"]},
    ])
    assert t.kcal == (513 - 90) + 289 + 147
    assert t.low == (513 - 112) + 289 + 147
    assert t.confidence == "中" and t.missing == []


def test_missing_part_listed_but_rest_summed():
    t = sum_nutrition([("中薯条", item_nutrition("4810", "中薯条")), ("神秘新品", None)])
    assert t.kcal == 289 and t.missing == ["神秘新品"]
