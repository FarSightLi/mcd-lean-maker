"""Pull one store's menu into web/snapshot (maintainer-only, needs MCD_MCP_TOKEN)."""
import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from pathlib import Path

from mcdcalc.offers import yuan_to_fen
from mcp_client import call

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web" / "snapshot"
FIXTURE = ROOT / "tests" / "fixtures" / "modification-options.raw.json"
GOLD_DISCOUNT = "随单购麦金卡优惠"


def removable_mods(modification):
    return [{"code": v["code"], "name": v["name"]}
            for item in (modification or {}).get("items", []) for v in item.get("values", [])
            if v.get("unselectedKey")]


def diff_fen(text: str) -> int:
    sign = -1 if text.strip().startswith("-") else 1
    return sign * yuan_to_fen(text.split("¥")[1].strip())


def base_price_fen(meal: dict) -> int:
    return yuan_to_fen(meal["originalPrice"] if meal.get("discountType") == GOLD_DISCOUNT else meal["currentPrice"])


def parse_gold(code: str, price_data: dict) -> dict:
    lines = price_data["productList"]
    item = next(line for line in lines if line["productCode"] == code)
    return {"priceFen": item["subtotal"], "feeFen": sum(l["subtotal"] for l in lines if l["productCode"] != code)}


def normalize_product(code, meal, detail, categories, tags, gold):
    rounds = [{"name": r["name"], "choices": [
        {"code": c["code"], "name": c["name"], "isDefault": c.get("isDefault") == 1,
         "diffFen": diff_fen(c.get("diffPrice", "+ ¥0")), "mods": removable_mods(c.get("modification"))}
        for c in r["choices"]]} for r in detail.get("rounds") or []]
    return {"code": code, "name": detail["name"], "image": meal.get("image"), "categories": categories,
            "tags": tags, "isNew": any("上新" in t for t in tags), "isCombo": bool(rounds),
            "priceFen": base_price_fen(meal), "originalFen": yuan_to_fen(meal["originalPrice"]), "gold": gold,
            "mods": removable_mods(detail.get("modification")), "rounds": rounds}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", default="1950564")
    ap.add_argument("--store-name", default="麦当劳北京建外SOHO(A座)餐厅")
    args = ap.parse_args()
    base = {"storeCode": args.store, "orderType": 1, "beType": 1}
    menu = call("query-meals", base)["data"]
    cats, tags = {}, {}
    for c in menu["categories"]:
        for m in c["meals"]:
            cats.setdefault(m["code"], []).append(c["name"].replace("\n", ""))
            tags.setdefault(m["code"], set()).update(m.get("tags", []))

    def fetch(code):
        meal = menu["meals"][code]
        detail = call("query-meal-detail", {**base, "code": code})
        if not detail.get("success"):
            return None
        gold = None
        w = meal.get("withOrder")
        if meal.get("canWithOrder") and w:
            r = call("calculate-price", {**base, "items": [{"productCode": code, "quantity": 1}],
                                         "withOrder": {"membershipCode": w["membershipCode"], "membershipSpecId": w["specId"]}})
            gold = parse_gold(code, r["data"]) if r.get("success") else None
        return normalize_product(code, meal, detail["data"], cats.get(code, []), sorted(tags.get(code, [])), gold)

    with ThreadPoolExecutor(6) as ex:
        products = sorted((p for p in ex.map(fetch, menu["meals"]) if p), key=lambda p: p["code"])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "products.json").write_text(json.dumps(products, ensure_ascii=False, indent=1), encoding="utf-8")
    meta = {"storeCode": args.store, "storeName": args.store_name, "productCount": len(products),
            "snapshotAt": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M"),
            "source": "麦当劳 MCP query-meals / query-meal-detail / calculate-price"}
    (OUT / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    options = {}
    for p in products:
        for m in p["mods"] + [m for r in p["rounds"] for c in r["choices"] for m in c["mods"]]:
            options.setdefault(m["code"], {"name": m["name"]})
    FIXTURE.write_text(json.dumps({"store": args.store, "options": dict(sorted(options.items()))},
                                  ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"products={len(products)} mods={len(options)}")


if __name__ == "__main__":
    main()
