import json
import time

from build_web import build, build_categories


def test_build_outputs(tmp_path):
    start = time.time()
    sizes = build(tmp_path)
    assert time.time() - start < 120
    assert set(sizes) == {"items.json", "recommend.json", "meta.json", "categories.json"}
    assert sum(sizes.values()) <= 3_000_000

    items = json.loads((tmp_path / "items.json").read_text(encoding="utf-8"))
    bigmac = items["1100"]
    names = [m["name"] for m in bigmac["mods"]]
    mask = (1 << names.index("巨无霸酱")) | (1 << names.index("吉士"))
    assert bigmac["results"]["0"]["kcal"] == 513
    assert bigmac["results"][str(mask)]["kcal"] == 377
    assert len(bigmac["results"]) == 2 ** len(names)

    rec = json.loads((tmp_path / "recommend.json").read_text(encoding="utf-8"))
    assert len(rec["grid"]) == 71 * 131
    plans = rec["grid"]["3000_700"]
    assert len(plans) == 3
    cheapest = rec["bundles"][plans[0]]
    assert cheapest["bestFen"] <= 3000 and cheapest["kcal"] <= 700
    assert all({"bestFen", "needsGold", "goldFeeFen"} <= set(b) for b in rec["bundles"])

    cats = json.loads((tmp_path / "categories.json").read_text(encoding="utf-8"))
    assert cats[0]["name"] == "500大卡套餐" and cats[0]["lean"] and cats[0]["label"] == "500\n大卡套餐"
    assert [c["name"] for c in cats[1:4]] == ["人气热卖", "精选单人餐", "鸡肉汉堡/卷"]
    assert len(cats) == 15 and all(i["code"] in items for c in cats for i in c["items"])
    assert "categories" not in json.loads((tmp_path / "meta.json").read_text(encoding="utf-8"))


def test_build_categories_order_tags_and_filter():
    tree = [{"name": "人气热卖", "items": [{"code": "a", "tags": ["爆款"]}, {"code": "x", "tags": []}]},
            {"name": "500\n大卡套餐", "items": [{"code": "a", "tags": ["套餐"]}]},
            {"name": "空", "items": [{"code": "c", "tags": []}]}]
    items = {"a": {}, "c": {"choiceOnly": True}}
    assert build_categories(tree, items) == [
        {"name": "500大卡套餐", "label": "500\n大卡套餐", "lean": True, "items": [{"code": "a", "tags": ["套餐"]}]},
        {"name": "人气热卖", "label": "人气热卖", "lean": False, "items": [{"code": "a", "tags": ["爆款"]}]}]
    assert build_categories(None, items) == []
