"""Precompute everything the static demo page needs into web/data."""
import json
import logging
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

from mcdcalc.nutrition import item_nutrition, mod_delta
from mcdcalc.offers import quote
from recommend import BUDGETS, KCAL_CAPS, build_bundles, build_options, recommend_grid

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "web" / "snapshot"
MAX_BYTES = 3_000_000
IMG_HOST = "menu-img.mcd.cn"
IMG_DIR = "img"
IMG_TIMEOUT = 15
IMG_WORKERS = 8
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
log = logging.getLogger("build_web")
RESULT_KEYS = ("kcal", "low", "high", "kj", "protein", "fat", "carbohydrate", "sodium", "calcium",
               "confidence", "adjusted", "estimated")


def _r1(v):
    return round(v, 1) if isinstance(v, float) else v


def _mod_info(code, m):
    d = mod_delta(code, m["code"])
    return {"code": m["code"], "name": m["name"], "kcal": d["kcal"], "range": d["range"], "confidence": d["confidence"]}


def _results(code, name, mods):
    if item_nutrition(code, name) is None:
        return None
    out = {}
    for mask in range(2 ** len(mods)):
        removed = [m["code"] for i, m in enumerate(mods) if mask >> i & 1]
        n = asdict(item_nutrition(code, name, removed))
        out[str(mask)] = {k: _r1(n[k]) for k in RESULT_KEYS}
    return out


def build_items(products):
    items = {}

    def add(code, name, mods, extra):
        if code not in items:
            base = item_nutrition(code, name)
            items[code] = {"name": name, "mods": [_mod_info(code, m) for m in mods],
                           "results": _results(code, name, mods),
                           "description": base.description if base else None, **extra}

    for p in products:
        add(p["code"], p["name"], p["mods"], {
            "image": p.get("image"), "categories": p["categories"], "isNew": p["isNew"], "isCombo": p["isCombo"],
            "priceFen": p["priceFen"], "originalFen": p["originalFen"], "gold": p["gold"],
            "rounds": [{"name": r["name"], "choices": [{"code": c["code"], "isDefault": c["isDefault"],
                                                        "diffFen": c["diffFen"]} for c in r["choices"]]}
                       for r in p["rounds"]]})
        for r in p["rounds"]:
            for c in r["choices"]:
                add(c["code"], c["name"], c["mods"], {"choiceOnly": True})
    return items


def _bundle_json(b):
    q = quote([{"priceFen": o.price_fen, "originalFen": o.price_fen, "qty": 1, "gold": o.gold} for o in b.options])
    return {"items": [{"code": o.code, "name": o.name, "variant": o.variant, "removed": list(o.removed_names)}
                      for o in b.options],
            "priceFen": b.price_fen, "gold": {"goldFen": q.gold_fen, "verdict": q.verdict} if q.gold_fen else None,
            "kcal": b.kcal, "low": b.low, "high": b.high, "protein": b.protein, "confidence": b.confidence,
            "kj": round(b.kj), "fat": _r1(b.fat), "carbohydrate": _r1(b.carbohydrate), "sodium": _r1(b.sodium),
            "calcium": _r1(b.calcium), "estimated": list(b.estimated),
            "bestFen": b.best_fen, "needsGold": b.needs_gold, "goldFeeFen": b.gold_fee_fen}


def build_recommend(products):
    grid = recommend_grid(build_bundles(build_options(products)))
    bundles, index = [], {}
    out = {}
    for (budget, cap), plans in grid.items():
        idxs = []
        for key in ("cheapest", "lightest", "protein"):
            b = plans.get(key)
            if b is None:
                continue
            ident = id(b)
            if ident not in index:
                index[ident] = len(bundles)
                bundles.append(_bundle_json(b))
            idxs.append(index[ident])
        out[f"{budget}_{cap}"] = idxs
    return {"budgets": list(BUDGETS), "caps": list(KCAL_CAPS), "bundles": bundles, "grid": out}


LEAN_CATEGORY = "500大卡套餐"


def build_categories(tree, items):
    """Ordered categories for the menu UI; the official 500 kcal category is pinned first."""
    out = []
    for c in tree or []:
        name = c["name"].replace("\n", "")
        kept = [i for i in c["items"] if i["code"] in items and not items[i["code"]].get("choiceOnly")]
        if kept:
            out.append({"name": name, "label": c["name"], "lean": name == LEAN_CATEGORY, "items": kept})
    return sorted(out, key=lambda c: not c["lean"])


def build_payload(products: list, meta: dict) -> dict[str, object]:
    meta = dict(meta)
    tree = meta.pop("categories", None)
    items = build_items(products)
    meta.update({"builtAt": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M"),
                 "budgets": [BUDGETS.start, BUDGETS.stop - 1, BUDGETS.step],
                 "caps": [KCAL_CAPS.start, KCAL_CAPS.stop - 1, KCAL_CAPS.step],
                 "confidenceNote": "官方=营养表原值;高/中/低=特制项或新品估算"})
    return {"items.json": items, "categories.json": build_categories(tree, items), "recommend.json": build_recommend(products), "meta.json": meta}


def image_filename(url):
    """Local file name for an allowed menu image URL, or None if the URL is rejected."""
    if not isinstance(url, str):
        return None
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or parts.hostname != IMG_HOST:
        return None
    name = urllib.parse.unquote(parts.path.rsplit("/", 1)[-1])
    if not _SAFE_NAME.match(name) or ".." in name:
        return None
    return name


def _fetch(url, dest, retries=1):
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=IMG_TIMEOUT) as resp:
                data = resp.read()
            if not data:
                raise ValueError("empty body")
            tmp = dest.with_name(dest.name + ".part")
            tmp.write_bytes(data)
            tmp.replace(dest)
            return True
        except Exception as e:  # noqa: BLE001 单张失败只告警
            if attempt == retries:
                log.warning("图片下载失败 %s: %s", url, e)
            else:
                time.sleep(0.5)
    return False


def download_images(items, out_dir):
    """Download item images into out_dir/img and set imageLocal; failures keep the remote image only."""
    img_dir = out_dir / IMG_DIR
    img_dir.mkdir(parents=True, exist_ok=True)
    jobs = {}
    for it in items.values():
        name = image_filename(it.get("image"))
        if name is None:
            if it.get("image"):
                log.warning("拒绝非白名单图片 %s", it.get("image"))
            continue
        jobs.setdefault(name, it["image"])
    stats = {"total": len(jobs), "downloaded": 0, "skipped": 0, "failed": 0}

    def run(name):
        dest = img_dir / name
        if dest.is_file() and dest.stat().st_size > 0:
            return name, "skipped"
        return name, "downloaded" if _fetch(jobs[name], dest) else "failed"

    ok = set()
    with ThreadPoolExecutor(max_workers=IMG_WORKERS) as pool:
        for name, result in pool.map(run, jobs):
            stats[result] += 1
            if result != "failed":
                ok.add(name)
    for it in items.values():
        name = image_filename(it.get("image"))
        if name in ok:
            it["imageLocal"] = f"data/{IMG_DIR}/{name}"
    stats["bytes"] = sum((img_dir / n).stat().st_size for n in ok)
    return stats


def build(out_dir: Path, images: bool = True) -> dict:
    products = json.loads((SNAP / "products.json").read_text(encoding="utf-8"))
    meta = json.loads((SNAP / "meta.json").read_text(encoding="utf-8"))
    out_dir.mkdir(parents=True, exist_ok=True)
    files = build_payload(products, meta)
    if images:
        print("images:", download_images(files["items.json"], out_dir))
    sizes = {}
    for name, obj in files.items():
        data = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
        (out_dir / name).write_text(data, encoding="utf-8")
        sizes[name] = len(data.encode())
    if sum(sizes.values()) > MAX_BYTES:
        raise SystemExit(f"web/data 超出 {MAX_BYTES} 字节: {sizes}")
    return sizes


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    print(build(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "web" / "data"))
