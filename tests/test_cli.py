import json
import subprocess
import sys
from pathlib import Path

CLI = Path(__file__).resolve().parents[1] / "skill" / "mcd-lean-maker" / "scripts" / "calc.py"


def run(cmd, payload):
    p = subprocess.run([sys.executable, str(CLI), cmd], input=json.dumps(payload), capture_output=True, text=True)
    return p.returncode, (json.loads(p.stdout) if p.stdout else None), p.stderr


def test_nutrition_combo():
    code, out, _ = run("nutrition", {"parts": [{"code": "1100", "name": "巨无霸", "removed": ["100116", "100141"]},
                                               {"code": "4810", "name": "中薯条"}]})
    assert code == 0 and out["kcal"] == 377 + 289 and out["missing"] == []


def test_mods_lists_delta():
    code, out, _ = run("mods", {"code": "1120", "mods": [{"code": "100141", "name": "吉士"}]})
    assert code == 0 and out[0]["kcal"] == 92


def test_quote_gold():
    line = {"priceFen": 5700, "originalFen": 5700, "qty": 1, "gold": {"priceFen": 2800, "feeFen": 1900}}
    code, out, _ = run("quote", {"lines": [line]})
    assert code == 0 and out["verdict"] == "开卡省¥10"


def test_bad_input_exit_2():
    code, _, err = run("nutrition", {"oops": 1})
    assert code == 2 and "parts" in err


def test_unknown_command_exit_2():
    code, _, err = run("bogus", {})
    assert code == 2 and "usage" in err


def _product(code, name, cat, price, mods=()):
    return {"code": code, "name": name, "categories": [cat], "isCombo": False, "priceFen": price,
            "gold": None, "mods": [{"code": c, "name": n} for c, n in mods], "rounds": []}


def test_plan_three_plans():
    products = [_product("1100", "巨无霸", "巨无霸牛鱼肉堡", 2550, [("100116", "巨无霸酱"), ("100141", "吉士")]),
                _product("1000", "汉堡包", "巨无霸牛鱼肉堡", 1200),
                _product("3050", "可乐中杯", "饮品", 1000)]
    code, out, _ = run("plan", {"products": products, "budgetFen": 3000, "kcalCap": 400})
    assert code == 0 and set(out) == {"cheapest", "lightest", "protein"}
    best = out["protein"]
    assert best["items"][0]["code"] == "1100" and best["items"][0]["removed"] == ["100116", "100141"]
    assert best["kcal"] == 377 and best["bestFen"] <= 3000


def test_plan_nothing_fits_returns_empty():
    code, out, _ = run("plan", {"products": [_product("1000", "汉堡包", "巨无霸牛鱼肉堡", 1200)],
                                "budgetFen": 500, "kcalCap": 400})
    assert code == 0 and out == {}


def test_mods_unknown_code_marks_no_data():
    code, out, _ = run("mods", {"code": "1100", "mods": [{"code": "999999", "name": "神秘酱"}]})
    assert code == 0 and out[0]["kcal"] is None and out[0]["confidence"] == "暂无数据"
