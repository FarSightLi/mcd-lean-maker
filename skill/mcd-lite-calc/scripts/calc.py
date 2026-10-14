"""mcd-lite-calc CLI: stdin JSON -> stdout JSON. Offline, no token."""
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcdcalc.nutrition import combo_nutrition, mod_delta  # noqa: E402
from mcdcalc.offers import quote  # noqa: E402


def cmd_nutrition(req):
    return asdict(combo_nutrition(req["parts"]))


def cmd_mods(req):
    return [{"code": m["code"], "name": m["name"], **{k: mod_delta(req["code"], m["code"])[k]
                                                       for k in ("kcal", "range", "confidence")}}
            for m in req["mods"]]


def cmd_quote(req):
    q = quote(req["lines"])
    return {"priceFen": q.price_fen, "originalFen": q.original_fen, "goldFen": q.gold_fen,
            "goldFeeFen": q.gold_fee_fen, "verdict": q.verdict}


COMMANDS = {"nutrition": cmd_nutrition, "mods": cmd_mods, "quote": cmd_quote}


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
        sys.exit(f"usage: calc.py {{{'|'.join(COMMANDS)}}} < input.json")
    try:
        out = COMMANDS[sys.argv[1]](json.load(sys.stdin))
    except (KeyError, TypeError, json.JSONDecodeError) as e:
        print(f"输入错误: 缺少或无效字段 {e}", file=sys.stderr)
        sys.exit(2)
    json.dump(out, sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    main()
