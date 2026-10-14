import json
import time

from build_web import build


def test_build_outputs(tmp_path):
    start = time.time()
    sizes = build(tmp_path)
    assert time.time() - start < 120
    assert set(sizes) == {"items.json", "recommend.json", "meta.json"}
    assert sum(sizes.values()) <= 3_000_000

    items = json.loads((tmp_path / "items.json").read_text(encoding="utf-8"))
    bigmac = items["1100"]
    names = [m["name"] for m in bigmac["mods"]]
    mask = (1 << names.index("巨无霸酱")) | (1 << names.index("吉士"))
    assert bigmac["results"]["0"]["kcal"] == 513
    assert bigmac["results"][str(mask)]["kcal"] == 377
    assert len(bigmac["results"]) == 2 ** len(names)

    rec = json.loads((tmp_path / "recommend.json").read_text(encoding="utf-8"))
    assert len(rec["grid"]) == 36 * 27
    plans = rec["grid"]["3000_700"]
    assert len(plans) == 3
    cheapest = rec["bundles"][plans[0]]
    assert cheapest["priceFen"] <= 3000 and cheapest["kcal"] <= 700
