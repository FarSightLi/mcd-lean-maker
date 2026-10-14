from mcdcalc.data import load, normalize, nutrition_index, parse_nutrition_text

SAMPLE = (
    "[3]{productName,nutritionDescription,energyKj,energyKcal,protein,fat,carbohydrate,sodium,calcium}:\n"
    "  汉堡包,null,1039,248,13,8,29,492,61\n"
    "  纯悦,能量约清水1杯,0,0,0,0,0,0,0\n"
    "  汉堡包,null,1039,248,13,8,29,492,61\n"
)


def test_parse_nutrition_text_dedupes_and_types():
    rows = parse_nutrition_text(SAMPLE)
    assert [r["name"] for r in rows] == ["汉堡包", "纯悦"]
    assert rows[0]["energyKcal"] == 248 and rows[0]["description"] is None
    assert rows[1]["description"] == "能量约清水1杯"


def test_normalize_fullwidth_and_spaces():
    assert normalize("雪碧（小杯）") == "雪碧(小杯)"
    assert normalize("100% 苹果汁") == "100%苹果汁"


def test_bundled_nutrition_snapshot():
    idx = nutrition_index()
    assert idx["巨无霸"]["energyKcal"] == 513
    assert idx["吉士汉堡包"]["energyKcal"] - idx["汉堡包"]["energyKcal"] == 46
    assert len(load("nutrition.json")) == len(idx)
