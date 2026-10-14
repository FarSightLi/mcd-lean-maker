"""Menu price, gold-card net price and one-coupon-per-order selection. Money is int fen."""
from dataclasses import dataclass
from decimal import Decimal


def yuan_to_fen(v) -> int:
    return int((Decimal(str(v)) * 100).to_integral_value())


def _yuan(fen: int) -> str:
    # "10.00" -> "10", "12.50" -> "12.5"
    return f"{Decimal(fen) / 100:.2f}".rstrip("0").rstrip(".")


@dataclass
class Quote:
    price_fen: int
    original_fen: int
    gold_fen: int | None
    gold_fee_fen: int
    verdict: str


def quote(lines) -> Quote:
    price = sum(l["priceFen"] * l["qty"] for l in lines)
    original = sum(l["originalFen"] * l["qty"] for l in lines)
    golds = [l for l in lines if l.get("gold")]
    if not golds:
        return Quote(price, original, None, 0, "无麦金卡价")
    fee = max(l["gold"]["feeFen"] for l in golds)
    gold = sum((l["gold"]["priceFen"] if l.get("gold") else l["priceFen"]) * l["qty"] for l in lines) + fee
    diff = price - gold
    verdict = f"开卡省¥{_yuan(diff)}" if diff > 0 else f"开卡更贵¥{_yuan(-diff)}"
    return Quote(price, original, gold, fee, verdict)


def _off(total_fen, codes, c) -> int:
    if c["type"] == "threshold":
        return c["offFen"] if total_fen >= c["minFen"] else 0
    if c["type"] == "item_price" and c["productCode"] in codes:
        return c["originalFen"] - c["priceFen"]
    return 0


def best_coupon(total_fen, codes, coupons):
    best = max(((c, _off(total_fen, codes, c)) for c in coupons), key=lambda x: x[1], default=(None, 0))
    return best if best[1] > 0 else (None, 0)
