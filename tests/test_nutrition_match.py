import mcdcalc.nutrition as nutrition_module
from mcdcalc.nutrition import match


def test_exact_match_official():
    n = match("1100", "巨无霸")
    assert (n.kcal, n.low, n.high, n.source, n.confidence) == (513, 513, 513, "exact", "官方")


def test_alias_match():
    n = match(None, "雪碧（小杯）")
    assert n.kcal == 76 and n.source == "alias" and n.confidence == "官方"


def test_derived_match_carries_range_and_confidence():
    n = match("521952", "龙焰鸡腿堡")
    assert (n.kcal, n.low, n.high, n.source, n.confidence) == (475, 440, 520, "derived", "低")


def test_no_fuzzy_match():
    assert match(None, "三层吉士汉堡") is None
    assert match(None, "吉士汉堡") is None  # 营养表里叫"吉士汉堡包"


def test_alias_match_by_product_code(monkeypatch):
    real_load = nutrition_module.load

    def fake_load(name):
        if name == "aliases.json":
            return {"1100": "巨无霸"}
        return real_load(name)

    monkeypatch.setattr(nutrition_module, "load", fake_load)

    n = match("1100", "不同的显示名")
    assert n.source == "alias" and n.kcal == 513
