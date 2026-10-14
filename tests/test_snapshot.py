from snapshot import base_price_fen, diff_fen, normalize_product, parse_gold, removable_mods

ICE = {"items": [{"values": [{"code": "200002", "name": "去冰", "selectedKey": "0-0"}]}]}
SAUCE = {"items": [{"values": [{"code": "100116", "name": "巨无霸酱", "selectedKey": "0-1", "unselectedKey": "0-0"}]}]}


def test_removable_mods_skip_ice():
    assert removable_mods(ICE) == [] and removable_mods(None) == []
    assert removable_mods(SAUCE) == [{"code": "100116", "name": "巨无霸酱"}]


def test_diff_fen():
    assert (diff_fen("+ ¥1.5"), diff_fen("- ¥0.5"), diff_fen("+ ¥0")) == (150, -50, 0)


def test_base_price_for_gold_card_menu_item():
    meal = {"currentPrice": "28", "originalPrice": "57", "discountType": "随单购麦金卡优惠"}
    assert base_price_fen(meal) == 5700
    assert base_price_fen({"currentPrice": "29.9", "originalPrice": "50.5", "discountType": "促销优惠"}) == 2990


def test_parse_gold_real_response():
    data = {"productList": [
        {"productCode": "9900000891", "subtotal": 2800},
        {"productCode": "513817", "productName": "麦金卡月卡（30天）", "subtotal": 1900}]}
    assert parse_gold("9900000891", data) == {"priceFen": 2800, "feeFen": 1900}


def test_normalize_combo():
    detail = {"name": "巨无霸套餐", "rounds": [{"name": "主食", "choices": [
        {"code": "1100", "name": "巨无霸", "isDefault": 1, "diffPrice": "+ ¥0", "modification": SAUCE}]}]}
    meal = {"currentPrice": "38", "originalPrice": "45", "image": "https://menu-img.mcd.cn/x.png"}
    p = normalize_product("99", meal, detail, ["巨无霸牛鱼肉堡"], ["套餐", "上新"], None)
    assert p["isCombo"] and p["isNew"] and p["priceFen"] == 3800 and p["originalFen"] == 4500
    assert p["rounds"][0]["choices"][0] == {"code": "1100", "name": "巨无霸", "isDefault": True,
                                             "diffFen": 0, "mods": [{"code": "100116", "name": "巨无霸酱"}]}
