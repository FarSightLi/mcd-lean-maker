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


def test_nutrition_returns_full_fields():
    code, out, _ = run("nutrition", {"parts": [{"code": "1100", "name": "巨无霸", "removed": ["100141"]}]})
    assert code == 0 and {"kj", "fat", "carbohydrate", "sodium", "calcium", "estimated"} <= set(out)
    assert out["calcium"] is not None and "kj" in out["estimated"]


def test_plan_not_exposed():
    code, _, err = run("plan", {})
    assert code == 2 and "usage" in err


def test_mods_unknown_code_marks_no_data():
    code, out, _ = run("mods", {"code": "1100", "mods": [{"code": "999999", "name": "神秘酱"}]})
    assert code == 0 and out[0]["kcal"] is None and out[0]["confidence"] == "暂无数据"
