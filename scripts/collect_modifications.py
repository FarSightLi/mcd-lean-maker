"""Collect all modification options from a store's full menu (read-only MCP calls)."""
import json
import os
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

MCP_URL = os.environ.get("MCD_MCP_URL", "https://mcp.mcd.cn")
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def load_token():
    token = os.environ.get("MCD_MCP_TOKEN")
    if token:
        return token
    cfg = json.load(open(os.path.expanduser("~/.claude.json")))
    proj = cfg["projects"]["/Users/lilongsheng/MyPrivate/McDonald"]["mcpServers"]["mcd-mcp"]
    return proj["headers"]["Authorization"].removeprefix("Bearer ").strip()


TOKEN = load_token()


def call(tool, args):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": tool, "arguments": args}}).encode()
    req = urllib.request.Request(MCP_URL, data=body, headers={
        "Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"})
    raw = urllib.request.urlopen(req, timeout=30).read().decode()
    # streamable http may answer as SSE
    if raw.lstrip().startswith("event:") or "\ndata:" in raw or raw.startswith("data:"):
        raw = [l[5:] for l in raw.splitlines() if l.startswith("data:")][-1]
    text = json.loads(raw)["result"]["content"][0]["text"]
    # text is markdown with the JSON payload embedded after the field docs
    start = text.find('{"success"')
    obj, _ = json.JSONDecoder().raw_decode(text[start:])
    return obj


def main(store):
    base = {"storeCode": store, "orderType": 1, "beType": 1}
    menu = call("query-meals", base)["data"]
    meals = menu["meals"]
    cat_of = {}
    for c in menu["categories"]:
        for m in c["meals"]:
            cat_of.setdefault(m["code"], {"category": c["name"].replace("\n", ""), "tags": m.get("tags", [])})

    def detail(code):
        try:
            return code, call("query-meal-detail", {**base, "code": code})
        except Exception as e:  # keep going on single failures
            return code, {"success": False, "message": str(e)}

    with ThreadPoolExecutor(8) as ex:
        details = dict(ex.map(detail, list(meals)))

    products, options, non_caloric, failed = {}, {}, {}, []

    def collect(code, name, mod):
        mod_codes = []
        for item in (mod or {}).get("items", []):
            for v in item.get("values", []):
                if v["code"] == "200002" or "unselectedKey" not in v:
                    non_caloric.setdefault(v["code"], set()).add(v["name"])
                    continue
                mod_codes.append(v["code"])
                o = options.setdefault(v["code"], {"name": v["name"], "maxQuantity": v["maxQuantity"], "products": {}})
                o["products"][code] = name
        return mod_codes

    for code, d in details.items():
        if not d.get("success"):
            failed.append({"code": code, "message": d.get("message")})
            continue
        data = d["data"]
        products[code] = {"name": data["name"], **cat_of.get(code, {}),
                          "isCombo": bool(data.get("rounds")),
                          "modCodes": collect(code, data["name"], data.get("modification"))}
        for r in data.get("rounds") or []:
            for ch in r["choices"]:
                if ch.get("supportModify"):
                    collect(ch["code"], ch["name"], ch.get("modification"))

    out = {"store": store, "mealCount": len(meals), "failed": failed,
           "options": {k: {**v, "products": [{"code": c, "name": n} for c, n in v["products"].items()]}
                       for k, v in sorted(options.items())},
           "nonCaloricOptions": {k: sorted(v) for k, v in non_caloric.items()}}
    json.dump(out, open(os.path.join(OUT_DIR, "modification-options.raw.json"), "w"), ensure_ascii=False, indent=1)
    json.dump(products, open(os.path.join(OUT_DIR, "products.raw.json"), "w"), ensure_ascii=False, indent=1)
    print(f"meals={len(meals)} products={len(products)} options={len(options)} failed={len(failed)}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "1950564")
