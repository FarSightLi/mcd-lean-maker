from mcdcalc.offers import best_coupon, quote, yuan_to_fen

SPICY = {"priceFen": 5700, "originalFen": 5700, "qty": 1, "gold": {"priceFen": 2800, "feeFen": 1900}}
FRIES = {"priceFen": 1250, "originalFen": 1250, "qty": 1, "gold": None}


def test_yuan_to_fen_exact():
    assert yuan_to_fen("25.5") == 2550 and yuan_to_fen("29.9") == 2990 and yuan_to_fen(15) == 1500


def test_gold_card_saves_real_case():
    q = quote([SPICY])  # 2026-10-14 实测:¥57 → ¥28 + 月卡 ¥19 = ¥47
    assert (q.price_fen, q.gold_fen, q.gold_fee_fen, q.verdict) == (5700, 4700, 1900, "开卡省¥10")


def test_gold_card_more_expensive():
    small = {**SPICY, "gold": {"priceFen": 5000, "feeFen": 1900}}
    assert quote([small]).verdict == "开卡更贵¥12"


def test_fee_counted_once_per_order():
    q = quote([SPICY, {**SPICY}, FRIES])
    assert q.gold_fen == 2800 * 2 + 1250 + 1900


def test_no_gold_lines():
    q = quote([FRIES])
    assert q.gold_fen is None and q.verdict == "无麦金卡价"


def test_best_coupon_one_per_order():
    coupons = [
        {"id": "a", "type": "threshold", "minFen": 3000, "offFen": 500},
        {"id": "b", "type": "item_price", "productCode": "4810", "priceFen": 600, "originalFen": 1250},
        {"id": "c", "type": "threshold", "minFen": 9000, "offFen": 2000},
    ]
    c, off = best_coupon(3500, ["4810", "1100"], coupons)
    assert c["id"] == "b" and off == 650
    assert best_coupon(1000, ["1100"], coupons) == (None, 0)
