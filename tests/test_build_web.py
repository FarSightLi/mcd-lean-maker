import json
import time

from build_web import _menu_rank, build, build_categories


def test_build_outputs(tmp_path):
    start = time.time()
    sizes = build(tmp_path, images=False)
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
    assert {"kj", "fat", "carbohydrate", "sodium", "calcium", "estimated"} <= set(bigmac["results"]["0"])
    assert bigmac["results"]["0"]["estimated"] == [] and "kj" in bigmac["results"][str(mask)]["estimated"]

    rec = json.loads((tmp_path / "recommend.json").read_text(encoding="utf-8"))
    assert len(rec["grid"]) == 71 * 131
    plans = rec["grid"]["3000_700"]
    assert len(plans) == 3
    assert rec["planOrder"] == ["lightest", "protein", "cheapest"]
    lightest, strongest, cheapest = (rec["bundles"][i] for i in plans)
    assert cheapest["bestFen"] <= 3000 and cheapest["kcal"] <= 700
    assert lightest["kcal"] <= cheapest["kcal"] and strongest["protein"] >= cheapest["protein"]
    for b in rec["bundles"]:
        for x in b["items"]:
            it = items[x["code"]]
            if it["isCombo"]:
                assert len(x["choices"]) == len(it["rounds"])
                removed = [m["name"] for c in x["choices"] if c
                           for i, m in enumerate(items[c["code"]]["mods"]) if c["mask"] >> i & 1]
            else:
                removed = [m["name"] for i, m in enumerate(it["mods"]) if x["mask"] >> i & 1]
            assert sorted(removed) == sorted(x["removed"]), x
    assert all({"bestFen", "needsGold", "goldFeeFen", "fat", "carbohydrate", "sodium", "kj", "calcium"} <= set(b)
               for b in rec["bundles"])
    assert all(len(b["items"]) >= 2 or items[b["items"][0]["code"]]["isCombo"] for b in rec["bundles"])   # 单项只能是套餐
    assert rec["grid"]["3000_400"] == [] or all(rec["bundles"][i]["kcal"] <= 400 for i in rec["grid"]["3000_400"])

    cats = json.loads((tmp_path / "categories.json").read_text(encoding="utf-8"))
    assert cats[0]["name"] == "500大卡套餐" and cats[0]["lean"] and cats[0]["label"] == "500\n大卡套餐"
    assert [c["name"] for c in cats[1:4]] == ["人气热卖", "精选单人餐", "鸡肉汉堡/卷"]
    assert len(cats) == 15 and all(i["code"] in items for c in cats for i in c["items"])
    for c in cats:
        ranks = [_menu_rank(items[i["code"]]) for i in c["items"]]
        assert ranks == sorted(ranks), c["name"]
    bigmac_cat = next(c for c in cats if any(items[i["code"]]["name"] == "巨无霸" for i in c["items"]))
    assert not items[bigmac_cat["items"][0]["code"]]["isCombo"]
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


def test_build_categories_items_first_combos_then_missing():
    tree = [{"name": "混合", "items": [{"code": "none", "tags": []}, {"code": "combo", "tags": []},
                                      {"code": "single", "tags": []}, {"code": "single2", "tags": []}]}]
    items = {"none": {"isCombo": False, "results": None}, "combo": {"isCombo": True, "results": {"0": {}}},
             "single": {"isCombo": False, "results": {"0": {}}}, "single2": {"isCombo": False, "results": {"0": {}}}}
    assert [i["code"] for i in build_categories(tree, items)[0]["items"]] == ["single", "single2", "combo", "none"]
