# mcd-lean-maker 麦麦减脂助手 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于麦当劳 MCP 做"去配料热量 + 优惠"计算:一个可安装的 Skill(实时、可下单)和一个静态演示页(快照、预计算)。

**Architecture:** 计算逻辑只有一份 Python 包 `mcdcalc`(纯函数、仅标准库),放在 Skill 目录内随 Skill 分发。`tools/snapshot.py` 由维护者本地用 Token 拉取 MCP 数据生成快照;`tools/build_web.py` 调 `mcdcalc` 把演示页需要的全部结果预计算成 JSON;`web/index.html` 只查表和渲染。

**Tech Stack:** Python ≥3.10 标准库、pytest 8.3.3(仅测试)、单文件 HTML/CSS/原生 JS、GitHub Actions + GitHub Pages、Netlify 镜像。

**Spec:** `docs/superpowers/specs/2026-10-14-mcd-lite-calc-design.md`

## Global Constraints

- `mcdcalc` 只用 Python 标准库,不联网,不读 Token
- 金额一律用"分"为单位的 int;元→分用 `Decimal`
- 营养匹配禁止模糊匹配;"双层/单层""大/中/小杯"是不同商品
- 热量区间:low = kcal − Σ被去除项 range 上限,high = kcal − Σ range 下限
- 置信度顺序:官方 > 高 > 中 > 低;组合结果取最低
- 演示页档位:预算 ¥10–¥80 步长 ¥1(71 档),热量 200–1500 kcal 步长 10(131 档)
- `web/data/` 总量 ≤ 3MB
- 页面不引用外部 CDN/字体/统计脚本;商品图可用 `menu-img.mcd.cn`
- 视觉仿麦当劳 App:主色 `#DA291C`、强调色 `#FFC72C`;不使用官方 Logo/金拱门图形/官方字体;页头页脚标"非官方 · 基于麦当劳 MCP 的参赛作品"
- Token 只来自环境变量 `MCD_MCP_TOKEN` 或平台 MCP 连接器;仓库与 CI 不含 Token;快照不含券、会员、订单数据
- 下单:明确"确认下单"才调 `create-order`;任何改动后重新核价、重出确认卡;一次确认一单
- 测试命令:`.venv/bin/python -m pytest -q`(项目根目录)
- 提交信息用中文、描述功能层面改动,结尾带 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`;在 `feature-mcd-lite-calc-20261014` 分支提交,不直接提交 master

## File Structure

```
pyproject.toml                                pytest 配置(pythonpath)
skill/mcd-lean-maker/
  SKILL.md                                    Skill 主线与安全规则
  references/mcp-tools.md                     用到的 MCP 工具与参数要点
  references/offers-rules.md                  优惠口径
  data/nutrition.json                         营养表快照(去重)
  data/modification-calories.json             特制项热量(由 data/ 迁入)
  data/aliases.json                           商品名/编码 → 营养表名称
  data/derived-nutrition.json                 营养表外商品推导值
  scripts/calc.py                             CLI
  scripts/mcdcalc/__init__.py
  scripts/mcdcalc/data.py                     加载数据、名称归一化、营养文本解析
  scripts/mcdcalc/nutrition.py                匹配、去配料重算、求和
  scripts/mcdcalc/offers.py                   元分转换、麦金卡净额、每单一券
  scripts/mcdcalc/recommend.py                候选、组合、档位推荐
tools/mcp_client.py                           本地 MCP 调用
tools/snapshot.py                             生成 web/snapshot 与 nutrition.json
tools/build_web.py                            生成 web/data/*.json
web/index.html                                演示页
web/snapshot/products.json · meta.json        快照(入库)
tests/fixtures/modification-options.raw.json  特制选项采集结果(由 data/ 迁入)
tests/test_*.py
.github/workflows/pages.yml · netlify.toml
README.md · MCP_INTEGRATION.md · CONTEST_DECLARATION.md · mcp-config.example.json
```

`data/products.raw.json` 与 `scripts/collect_modifications.py` 在 Task 7 删除(由 snapshot.py 取代)。

---

### Task 1: 项目骨架与数据加载

**Files:**
- Create: `pyproject.toml`, `skill/mcd-lean-maker/scripts/mcdcalc/__init__.py`, `skill/mcd-lean-maker/scripts/mcdcalc/data.py`, `tools/mcp_client.py`, `skill/mcd-lean-maker/data/nutrition.json`
- Move: `data/modification-calories.json` → `skill/mcd-lean-maker/data/`; `data/modification-options.raw.json` → `tests/fixtures/`
- Test: `tests/test_data.py`

**Interfaces:**
- Produces: `mcdcalc.data.DATA_DIR: Path`, `normalize(name: str) -> str`, `load(name: str) -> dict|list`(lru_cache), `parse_nutrition_text(text: str) -> list[dict]`(每行 `{"name","description","energyKj","energyKcal","protein","fat","carbohydrate","sodium","calcium"}`,同名只留第一条), `nutrition_index() -> dict[str, dict]`(归一化名称 → 行)
- Produces: `tools/mcp_client.call(tool: str, args: dict) -> dict`(返回 MCP 业务 JSON,即含 `success/data` 的对象)

- [ ] **Step 1: 建骨架、迁移数据**

```bash
mkdir -p skill/mcd-lean-maker/{data,references,scripts/mcdcalc} tools tests/fixtures web/snapshot
git mv data/modification-calories.json skill/mcd-lean-maker/data/
git mv data/modification-options.raw.json tests/fixtures/
touch skill/mcd-lean-maker/scripts/mcdcalc/__init__.py
```

`pyproject.toml`:

```toml
[tool.pytest.ini_options]
pythonpath = ["skill/mcd-lean-maker/scripts", "tools"]
testpaths = ["tests"]
```

- [ ] **Step 2: 写失败测试 `tests/test_data.py`**

```python
from mcdcalc.data import load, normalize, nutrition_index, parse_nutrition_text

SAMPLE = (
    "[3]{productName,nutritionDescription,energyKj,energyKcal,protein,fat,carbohydrate,sodium,calcium}:\n"
    "  汉堡包,null,1039,248,13,8,29,492,61\n"
    "  纯悦,能量约清水1杯,0,0,0,0,0,0,0\n"
    "  汉堡包,null,1039,248,13,8,29,492,61\n"
)


def test_parse_nutrition_text_dedupes_and_types():
    rows = parse_nutrition_text(SAMPLE)
    assert [r["name"] for r in rows] == ["汉堡包", "纯悦"]
    assert rows[0]["energyKcal"] == 248 and rows[0]["description"] is None
    assert rows[1]["description"] == "能量约清水1杯"


def test_normalize_fullwidth_and_spaces():
    assert normalize("雪碧（小杯）") == "雪碧(小杯)"
    assert normalize("100% 苹果汁") == "100%苹果汁"


def test_bundled_nutrition_snapshot():
    idx = nutrition_index()
    assert idx["巨无霸"]["energyKcal"] == 513
    assert idx["吉士汉堡包"]["energyKcal"] - idx["汉堡包"]["energyKcal"] == 46
    assert len(load("nutrition.json")) == len(idx)
```

- [ ] **Step 3: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_data.py -q`
Expected: FAIL,`ModuleNotFoundError: No module named 'mcdcalc.data'`

- [ ] **Step 4: 实现 `mcdcalc/data.py`**

```python
"""Bundled data loading and name normalization."""
import json
import unicodedata
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
NUTRITION_FIELDS = ("energyKj", "energyKcal", "protein", "fat", "carbohydrate", "sodium", "calcium")


def normalize(name: str) -> str:
    return unicodedata.normalize("NFKC", name).replace(" ", "").strip()


@lru_cache(maxsize=None)
def load(name: str):
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def parse_nutrition_text(text: str) -> list[dict]:
    """Parse the `data` text of list-nutrition-foods; keeps the first row per name."""
    rows, seen = [], set()
    for line in text.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        name, desc, *nums = line.rsplit(",", len(NUTRITION_FIELDS))
        if name in seen:
            continue
        seen.add(name)
        row = {"name": name, "description": None if desc == "null" else desc}
        row.update({k: float(v) for k, v in zip(NUTRITION_FIELDS, nums)})
        rows.append(row)
    return rows


@lru_cache(maxsize=None)
def nutrition_index() -> dict:
    return {normalize(r["name"]): r for r in load("nutrition.json")}
```

- [ ] **Step 5: 实现 `tools/mcp_client.py` 并生成 nutrition.json**

```python
"""Maintainer-only MCP client. Token comes from MCD_MCP_TOKEN."""
import json
import os
import urllib.request

MCP_URL = os.environ.get("MCD_MCP_URL", "https://mcp.mcd.cn")


def _token() -> str:
    token = os.environ.get("MCD_MCP_TOKEN")
    if not token:
        raise SystemExit("MCD_MCP_TOKEN 未设置")
    return token


def call(tool: str, args: dict) -> dict:
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": tool, "arguments": args}}).encode()
    req = urllib.request.Request(MCP_URL, data=body, headers={
        "Authorization": f"Bearer {_token()}", "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"})
    raw = urllib.request.urlopen(req, timeout=30).read().decode()
    if raw.startswith("event:") or raw.startswith("data:"):
        raw = [line[5:] for line in raw.splitlines() if line.startswith("data:")][-1]
    text = json.loads(raw)["result"]["content"][0]["text"]
    # the payload is embedded after markdown field docs
    obj, _ = json.JSONDecoder().raw_decode(text[text.find('{"success"'):])
    return obj
```

生成营养快照(维护者本地执行,Token 只在当前 shell):

```bash
export MCD_MCP_TOKEN=<你的 Token>
.venv/bin/python -c "
import json,sys; sys.path[:0]=['tools','skill/mcd-lean-maker/scripts']
from mcp_client import call; from mcdcalc.data import parse_nutrition_text
rows=parse_nutrition_text(call('list-nutrition-foods',{})['data'])
open('skill/mcd-lean-maker/data/nutrition.json','w').write(json.dumps(rows,ensure_ascii=False,indent=1)); print(len(rows))"
```

Expected: 打印 157 左右(160 行去重后)

- [ ] **Step 6: 运行测试通过**

Run: `.venv/bin/python -m pytest tests/test_data.py -q`
Expected: `3 passed`

- [ ] **Step 7: 提交**

```bash
git add pyproject.toml skill tools tests data
git commit -m "feat: 计算核心数据加载与营养表快照

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 2: 营养匹配(别名、精确、推导)

**Files:**
- Create: `skill/mcd-lean-maker/scripts/mcdcalc/nutrition.py`, `skill/mcd-lean-maker/data/aliases.json`, `skill/mcd-lean-maker/data/derived-nutrition.json`
- Test: `tests/test_nutrition_match.py`

**Interfaces:**
- Consumes: `mcdcalc.data.load/normalize/nutrition_index`
- Produces: `Nutrition`(frozen dataclass:`kcal, low, high: float; protein, fat, carbohydrate, sodium: float; confidence: str; source: str; adjusted: bool = True`), `match(code: str|None, name: str) -> Nutrition|None`, `CONF_RANK = {"官方":3,"高":2,"中":1,"低":0}`
- `source` 取值:`alias` / `exact` / `derived`

- [ ] **Step 1: 写数据文件**

`skill/mcd-lean-maker/data/aliases.json`(键为菜单商品名,值为营养表名称;也可用 productCode 作键):

```json
{
  "雪碧（小杯）": "雪碧小杯",
  "麦辣鸡翅2块": "麦辣鸡翅-2块",
  "100% 苹果汁(盒装)": "100%苹果汁",
  "麦咖啡™冰奶铁中杯": "冰奶铁中杯",
  "麦咖啡™冰美式中杯": "冰美式中杯",
  "阳光橙麦炫酷": "麦旋酷阳光橙"
}
```

`skill/mcd-lean-maker/data/derived-nutrition.json`(键为菜单商品名;数值为整品值,需写推导式):

```json
{
  "龙焰鸡腿堡": {
    "energyKcal": 475, "range": [440, 520], "protein": 24, "fat": 23, "carbohydrate": 42, "sodium": 1200,
    "confidence": "低", "derivation": "麦辣鸡腿汉堡485 − 麦香鸡酱70 + 辣椒黄油风味酱60;鸡腿排差异未知"
  },
  "龙焰芝士棒鸡腿堡": {
    "energyKcal": 575, "range": [520, 640], "protein": 28, "fat": 30, "carbohydrate": 48, "sodium": 1350,
    "confidence": "低", "derivation": "龙焰鸡腿堡475 + 马苏里拉芝士棒约100"
  },
  "高达吉士双牛堡": {
    "energyKcal": 437, "range": [400, 480], "protein": 27, "fat": 23, "carbohydrate": 31, "sodium": 1017,
    "confidence": "低", "derivation": "双层吉士汉堡429 − 两片吉士92 + 两片高达干酪片100"
  },
  "那么大鸡排（椒盐风味）": {
    "energyKcal": 385, "range": [360, 420], "protein": 24, "fat": 21, "carbohydrate": 24, "sodium": 1050,
    "confidence": "中", "derivation": "参照那么大鸡排385,椒盐调味热量可忽略,钠略增"
  }
}
```

- [ ] **Step 2: 写失败测试 `tests/test_nutrition_match.py`**

```python
from mcdcalc.nutrition import match


def test_exact_match_official():
    n = match("1100", "巨无霸")
    assert (n.kcal, n.low, n.high, n.source, n.confidence) == (513, 513, 513, "exact", "官方")


def test_alias_match():
    n = match(None, "雪碧（小杯）")
    assert n.kcal == 76 and n.source == "alias" and n.confidence == "官方"


def test_derived_match_carries_range_and_confidence():
    n = match("521952", "龙焰鸡腿堡")
    assert (n.kcal, n.low, n.high, n.source, n.confidence) == (475, 440, 520, "derived", "低")


def test_no_fuzzy_match():
    assert match(None, "三层吉士汉堡") is None
    assert match(None, "吉士汉堡") is None  # 营养表里叫"吉士汉堡包"
```

- [ ] **Step 3: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_nutrition_match.py -q`
Expected: FAIL,`ModuleNotFoundError: No module named 'mcdcalc.nutrition'`

- [ ] **Step 4: 实现 `mcdcalc/nutrition.py`(匹配部分)**

```python
"""Nutrition matching, modification removal and summing."""
from dataclasses import dataclass, replace

from mcdcalc.data import load, normalize, nutrition_index

CONF_RANK = {"官方": 3, "高": 2, "中": 1, "低": 0}


@dataclass(frozen=True)
class Nutrition:
    kcal: float
    low: float
    high: float
    protein: float
    fat: float
    carbohydrate: float
    sodium: float
    confidence: str
    source: str
    adjusted: bool = True


def _from_row(row: dict, source: str) -> Nutrition:
    k = row["energyKcal"]
    return Nutrition(k, k, k, row["protein"], row["fat"], row["carbohydrate"], row["sodium"], "官方", source)


def _lookup(table: dict, code, name):
    norm = {normalize(k): v for k, v in table.items()}
    if code and code in table:
        return table[code]
    return norm.get(normalize(name))


def match(code, name: str):
    idx = nutrition_index()
    alias = _lookup(load("aliases.json"), code, name)
    if alias and normalize(alias) in idx:
        return _from_row(idx[normalize(alias)], "alias")
    if normalize(name) in idx:
        return _from_row(idx[normalize(name)], "exact")
    d = _lookup(load("derived-nutrition.json"), code, name)
    if d:
        lo, hi = d["range"]
        return Nutrition(d["energyKcal"], lo, hi, d["protein"], d["fat"], d["carbohydrate"], d["sodium"],
                         d["confidence"], "derived")
    return None
```

- [ ] **Step 5: 运行测试通过**

Run: `.venv/bin/python -m pytest tests/test_nutrition_match.py -q`
Expected: `4 passed`

- [ ] **Step 6: 提交**

```bash
git add skill/mcd-lean-maker tests/test_nutrition_match.py
git commit -m "feat: 营养匹配支持别名、精确与新品推导

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 3: 去配料热量重算

**Files:**
- Modify: `skill/mcd-lean-maker/scripts/mcdcalc/nutrition.py`(追加)
- Test: `tests/test_nutrition_remove.py`

**Interfaces:**
- Consumes: `Nutrition`, `match`, `load("modification-calories.json")`
- Produces: `mod_delta(product_code: str, mod_code: str) -> dict`(返回 `{"name","kcal","range","confidence",["nutrients"]}`,商品级 override 优先;冰量等 nonCaloric 返回 `kcal=0`), `remove_mods(base: Nutrition, product_code: str, removed: list[str]) -> Nutrition`, `item_nutrition(code: str, name: str, removed: list[str] = ()) -> Nutrition|None`
- 规则:被去除项有 `nutrients` 则扣减四项营养素;kcal ≥ 10 且无 `nutrients` 时结果 `adjusted=False`;未知 mod code 抛 `KeyError`

- [ ] **Step 1: 写失败测试 `tests/test_nutrition_remove.py`**

```python
import pytest

from mcdcalc.nutrition import item_nutrition, mod_delta


def test_bigmac_remove_sauce_and_cheese():
    n = item_nutrition("1100", "巨无霸", ["100116", "100141"])
    assert n.kcal == 513 - 90 - 46 == 377
    assert (n.low, n.high) == (513 - 112 - 50, 513 - 70 - 44) == (351, 399)
    assert n.confidence == "中"           # 巨无霸酱为中
    assert n.adjusted is False            # 巨无霸酱无 nutrients
    assert n.protein == 27 - 3            # 吉士 nutrients 已扣


def test_override_double_cheese_two_slices():
    assert mod_delta("1120", "100141")["kcal"] == 92
    assert mod_delta("1100", "100141")["kcal"] == 46


def test_vegetables_keep_adjusted_true():
    n = item_nutrition("1100", "巨无霸", ["100168", "100202", "100212"])
    assert n.kcal == 513 - 5 and n.adjusted is True and n.confidence == "高"


def test_non_caloric_option_is_zero():
    assert mod_delta("3050", "200002")["kcal"] == 0


def test_unknown_mod_raises():
    with pytest.raises(KeyError):
        mod_delta("1100", "999999")


def test_unmatched_product_returns_none():
    assert item_nutrition("x", "不存在的堡", ["100141"]) is None
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_nutrition_remove.py -q`
Expected: FAIL,`ImportError: cannot import name 'item_nutrition'`

- [ ] **Step 3: 追加实现到 `nutrition.py`**

```python
NUTRIENT_KEYS = ("protein", "fat", "carbohydrate", "sodium")


def mod_delta(product_code: str, mod_code: str) -> dict:
    table = load("modification-calories.json")
    if mod_code in table.get("nonCaloric", {}):
        return {"name": "", "kcal": 0, "range": [0, 0], "confidence": "高"}
    base = table["options"][mod_code]
    override = table.get("overrides", {}).get(product_code, {}).get(mod_code)
    return {**base, **override} if override else base


def remove_mods(base: Nutrition, product_code: str, removed) -> Nutrition:
    n = base
    for code in removed:
        d = mod_delta(product_code, code)
        lo, hi = d["range"]
        nutrients = d.get("nutrients")
        changes = {"kcal": n.kcal - d["kcal"], "low": n.low - hi, "high": n.high - lo}
        if nutrients:
            changes.update({k: n.__dict__[k] - nutrients.get(k, 0) for k in NUTRIENT_KEYS})
        elif d["kcal"] >= 10:
            # tiny items (lettuce, onion) do not meaningfully move macros
            changes["adjusted"] = False
        if CONF_RANK[d["confidence"]] < CONF_RANK[n.confidence]:
            changes["confidence"] = d["confidence"]
        n = replace(n, **changes)
    return n


def item_nutrition(code: str, name: str, removed=()):
    base = match(code, name)
    return remove_mods(base, code, removed) if base else None
```

- [ ] **Step 4: 运行测试通过**

Run: `.venv/bin/python -m pytest tests/test_nutrition_remove.py -q`
Expected: `6 passed`

- [ ] **Step 5: 提交**

```bash
git add skill/mcd-lean-maker/scripts/mcdcalc/nutrition.py tests/test_nutrition_remove.py
git commit -m "feat: 去配料热量按特制项重算并给出区间与置信度

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 4: 套餐求和与数据自洽校验

**Files:**
- Modify: `skill/mcd-lean-maker/scripts/mcdcalc/nutrition.py`(追加)
- Test: `tests/test_nutrition_sum.py`, `tests/test_data_consistency.py`

**Interfaces:**
- Produces: `Total`(dataclass:`kcal, low, high, protein, fat, carbohydrate, sodium: float; confidence: str; adjusted: bool; missing: list[str]`), `sum_nutrition(parts: list[tuple[str, Nutrition|None]]) -> Total`, `combo_nutrition(selections: list[dict]) -> Total`(selection = `{"code","name","removed":[...]}`)

- [ ] **Step 1: 写失败测试 `tests/test_nutrition_sum.py`**

```python
from mcdcalc.nutrition import combo_nutrition, item_nutrition, sum_nutrition


def test_combo_sums_parts():
    t = combo_nutrition([
        {"code": "1100", "name": "巨无霸", "removed": ["100116"]},
        {"code": "4810", "name": "中薯条", "removed": []},
        {"code": "3050", "name": "可乐中杯", "removed": ["200002"]},
    ])
    assert t.kcal == (513 - 90) + 289 + 147
    assert t.low == (513 - 112) + 289 + 147
    assert t.confidence == "中" and t.missing == []


def test_missing_part_listed_but_rest_summed():
    t = sum_nutrition([("中薯条", item_nutrition("4810", "中薯条")), ("神秘新品", None)])
    assert t.kcal == 289 and t.missing == ["神秘新品"]
```

`tests/test_data_consistency.py`:

```python
import json
from pathlib import Path

from mcdcalc.data import load

FIX = Path(__file__).parent / "fixtures" / "modification-options.raw.json"


def test_every_collected_option_has_calories():
    collected = set(json.loads(FIX.read_text(encoding="utf-8"))["options"])
    table = load("modification-calories.json")["options"]
    assert collected == set(table)


def test_option_schema():
    for code, o in load("modification-calories.json")["options"].items():
        lo, hi = o["range"]
        assert lo <= o["kcal"] <= hi, code
        assert o["method"] in {"A", "B", "C"} and o["confidence"] in {"高", "中", "低"}, code


def test_derived_schema():
    for name, d in load("derived-nutrition.json").items():
        lo, hi = d["range"]
        assert lo <= d["energyKcal"] <= hi and d["derivation"], name
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_nutrition_sum.py tests/test_data_consistency.py -q`
Expected: FAIL,`ImportError: cannot import name 'combo_nutrition'`;consistency 测试应 PASS

- [ ] **Step 3: 追加实现**

```python
@dataclass
class Total:
    kcal: float = 0
    low: float = 0
    high: float = 0
    protein: float = 0
    fat: float = 0
    carbohydrate: float = 0
    sodium: float = 0
    confidence: str = "官方"
    adjusted: bool = True
    missing: list = None


def sum_nutrition(parts) -> Total:
    t = Total(missing=[])
    for name, n in parts:
        if n is None:
            t.missing.append(name)
            continue
        for k in ("kcal", "low", "high") + NUTRIENT_KEYS:
            setattr(t, k, getattr(t, k) + getattr(n, k))
        if CONF_RANK[n.confidence] < CONF_RANK[t.confidence]:
            t.confidence = n.confidence
        t.adjusted = t.adjusted and n.adjusted
    return t


def combo_nutrition(selections) -> Total:
    return sum_nutrition([(s["name"], item_nutrition(s["code"], s["name"], s.get("removed", [])))
                          for s in selections])
```

- [ ] **Step 4: 运行测试通过**

Run: `.venv/bin/python -m pytest -q`
Expected: 全部 PASS(Task 1–4 共 18 个)

- [ ] **Step 5: 提交**

```bash
git add skill/mcd-lean-maker/scripts/mcdcalc/nutrition.py tests/test_nutrition_sum.py tests/test_data_consistency.py
git commit -m "feat: 套餐营养按子项求和并校验特制热量数据完整

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 5: 优惠计算

**Files:**
- Create: `skill/mcd-lean-maker/scripts/mcdcalc/offers.py`
- Test: `tests/test_offers.py`

**Interfaces:**
- Produces:
  - `yuan_to_fen(v: str|float|int) -> int`
  - `Quote`(dataclass:`price_fen, original_fen: int; gold_fen: int|None; gold_fee_fen: int; verdict: str`)
  - `quote(lines: list[dict]) -> Quote`,line = `{"priceFen": int, "originalFen": int, "qty": int, "gold": {"priceFen": int, "feeFen": int}|None}`
  - `verdict` 取值:`"无麦金卡价"` / `"开卡省¥X"` / `"开卡更贵¥X"`(X 两位小数去尾零)
  - `best_coupon(total_fen: int, codes: list[str], coupons: list[dict]) -> tuple[dict|None, int]`,coupon = `{"id","type":"threshold","minFen","offFen"}` 或 `{"id","type":"item_price","productCode","priceFen","originalFen"}`;每单只取一张,返回 (券, 减免分)
- 麦金卡规则:卡费一单只计一次,取各行 `feeFen` 最大值;gold_fen = Σ(有 gold 的行用 gold.priceFen,否则 priceFen)×qty + fee

- [ ] **Step 1: 写失败测试 `tests/test_offers.py`**

```python
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
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_offers.py -q`
Expected: FAIL,`ModuleNotFoundError: No module named 'mcdcalc.offers'`

- [ ] **Step 3: 实现 `mcdcalc/offers.py`**

```python
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
```

- [ ] **Step 4: 运行测试通过**

Run: `.venv/bin/python -m pytest tests/test_offers.py -q`
Expected: `6 passed`

- [ ] **Step 5: 提交**

```bash
git add skill/mcd-lean-maker/scripts/mcdcalc/offers.py tests/test_offers.py
git commit -m "feat: 麦金卡净价判断与每单一券选择

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 6: 预算 × 热量推荐

**Files:**
- Create: `skill/mcd-lean-maker/scripts/mcdcalc/recommend.py`
- Test: `tests/test_recommend.py`

**Interfaces:**
- Consumes: `combo_nutrition`, `mod_delta`, `CONF_RANK`;商品快照结构(Task 7 生成,此处用合成数据):
  `{"code","name","categories":[str],"tags":[str],"isCombo":bool,"priceFen":int,"originalFen":int,"gold":{"priceFen","feeFen"}|None,"mods":[{"code","name"}],"rounds":[{"name","choices":[{"code","name","isDefault":bool,"diffFen":int,"mods":[{"code","name"}]}]}]}`
- Produces:
  - `Option`(dataclass:`code, name, variant("standard"|"light"); removed: tuple[(partCode, modCode)]; removed_names: tuple[str]; price_fen: int; gold: dict|None; kcal, low, high, protein: float; confidence: str; is_main, is_drink, is_combo: bool`)
  - `build_options(products) -> list[Option]`:每个有营养的商品出 standard;若存在 kcal ≥ 10 的可去项,再出 light(去掉这些项);套餐按各轮默认选项计算;任一部分无营养则跳过该商品
  - `Bundle`(dataclass:`options: tuple[Option]; price_fen: int; kcal, low, high, protein: float; confidence: str`)
  - `build_bundles(options, max_items=3) -> list[Bundle]`:1–3 个不同商品;主食 1–2 个;饮品 ≤ 1;套餐 ≤ 1,含套餐的组合最多 2 件(控制组合规模在 20 万以内)
  - `BUDGETS = range(1000, 8001, 200)`,`KCAL_CAPS = range(200, 1501, 50)`
  - `pick(bundles, budget_fen, kcal_cap) -> dict`:`{"cheapest","lightest","protein"}` 或 `{}`
  - `recommend_grid(bundles, budgets=BUDGETS, caps=KCAL_CAPS) -> dict[(budget, cap), dict]`,结果与逐格 `pick` 一致
- 排序规则:cheapest 按 (价格, kcal) 最小;lightest 按 (kcal, 价格) 最小;protein 按 (蛋白 最大, 价格 最小, kcal 最小)

- [ ] **Step 1: 写失败测试 `tests/test_recommend.py`**

```python
from mcdcalc.recommend import BUDGETS, KCAL_CAPS, build_bundles, build_options, pick, recommend_grid


def P(code, name, cat, price, mods=(), combo=False, rounds=None):
    return {"code": code, "name": name, "categories": [cat], "tags": [], "isCombo": combo,
            "priceFen": price, "originalFen": price, "gold": None,
            "mods": [{"code": c, "name": n} for c, n in mods], "rounds": rounds or []}


BIGMAC = P("1100", "巨无霸", "巨无霸牛鱼肉堡", 2550,
           [("100116", "巨无霸酱"), ("100141", "吉士"), ("100168", "生菜")])
HAMBURGER = P("1000", "汉堡包", "巨无霸牛鱼肉堡", 1200)
FRIES = P("4810", "中薯条", "小食甜品/其他", 1250)
COLA = P("3050", "可乐中杯", "饮品", 1000)
SPRITE = P("3060", "雪碧中杯", "饮品", 1000)
MERCH = P("9", "“葱不求人“按摩捶痒痒挠", "小食甜品/其他", 1990)
PRODUCTS = [BIGMAC, HAMBURGER, FRIES, COLA, SPRITE, MERCH]


def test_options_standard_and_light():
    opts = {(o.code, o.variant): o for o in build_options(PRODUCTS)}
    assert opts[("1100", "light")].kcal == 377
    assert opts[("1100", "light")].removed_names == ("巨无霸酱", "吉士")   # 生菜 < 10 kcal 不去
    assert ("4810", "light") not in opts
    assert not any(code == "9" for code, _ in opts)                      # 无营养数据的周边


def test_combo_uses_default_choices():
    combo = P("99", "巨无霸套餐", "巨无霸牛鱼肉堡", 3800, combo=True, rounds=[
        {"name": "主食", "choices": [{"code": "1100", "name": "巨无霸", "isDefault": True, "diffFen": 0,
                                    "mods": [{"code": "100116", "name": "巨无霸酱"}]}]},
        {"name": "饮料", "choices": [{"code": "3050", "name": "可乐中杯", "isDefault": True, "diffFen": 0, "mods": []},
                                   {"code": "3060", "name": "雪碧中杯", "isDefault": False, "diffFen": 0, "mods": []}]},
    ])
    opts = {o.variant: o for o in build_options([combo])}
    assert opts["standard"].kcal == 513 + 147 and opts["light"].kcal == 513 - 90 + 147
    assert opts["standard"].is_main and not opts["standard"].is_drink


def test_bundle_rules():
    bundles = build_bundles(build_options(PRODUCTS))
    for b in bundles:
        assert 1 <= sum(o.is_main for o in b.options) <= 2
        assert sum(o.is_drink for o in b.options) <= 1
        assert len({o.code for o in b.options}) == len(b.options)
        assert sum(o.is_combo for o in b.options) <= 1


def test_pick_three_plans():
    plans = pick(build_bundles(build_options(PRODUCTS)), 3000, 400)
    assert [o.code for o in plans["cheapest"].options] == ["1000"]
    assert [o.code for o in plans["lightest"].options] == ["1000"]
    best = plans["protein"].options
    assert [(o.code, o.variant) for o in best] == [("1100", "light")]
    assert pick([], 3000, 400) == {}


def test_grid_matches_pick_everywhere():
    bundles = build_bundles(build_options(PRODUCTS))
    grid = recommend_grid(bundles)
    assert len(grid) == len(BUDGETS) * len(KCAL_CAPS) == 36 * 27
    for (budget, cap), plans in grid.items():
        expect = pick(bundles, budget, cap)
        assert {k: v.price_fen for k, v in plans.items()} == {k: v.price_fen for k, v in expect.items()}
        assert {k: v.kcal for k, v in plans.items()} == {k: v.kcal for k, v in expect.items()}
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_recommend.py -q`
Expected: FAIL,`ModuleNotFoundError: No module named 'mcdcalc.recommend'`

- [ ] **Step 3: 实现 `mcdcalc/recommend.py`**

```python
"""Bundle search under budget x calorie caps."""
from dataclasses import dataclass
from itertools import combinations

from mcdcalc.nutrition import CONF_RANK, combo_nutrition, mod_delta

MAIN_CATEGORIES = {"鸡肉汉堡/卷", "巨无霸牛鱼肉堡", "安格斯MAX厚牛堡", "炸鸡", "蘸酱炸鸡"}
DRINK_CATEGORIES = {"饮品", "麦咖啡™"}
LIGHT_MIN_KCAL = 10
BUDGETS = range(1000, 8001, 200)
KCAL_CAPS = range(200, 1501, 50)


@dataclass
class Option:
    code: str
    name: str
    variant: str
    removed: tuple
    removed_names: tuple
    price_fen: int
    gold: dict | None
    kcal: float
    low: float
    high: float
    protein: float
    confidence: str
    is_main: bool
    is_drink: bool
    is_combo: bool


@dataclass
class Bundle:
    options: tuple
    price_fen: int
    kcal: float
    low: float
    high: float
    protein: float
    confidence: str


def _parts(p):
    if not p["isCombo"]:
        return [p]
    return [next((c for c in r["choices"] if c["isDefault"]), None) for r in p["rounds"]]


def _heavy(code, mods):
    return [m for m in mods if mod_delta(code, m["code"])["kcal"] >= LIGHT_MIN_KCAL]


def build_options(products):
    out = []
    for p in products:
        parts = _parts(p)
        if p.get("priceFen") is None or None in parts:
            continue
        cats = set(p["categories"])
        is_main = p["isCombo"] or bool(cats & MAIN_CATEGORIES)
        is_drink = not p["isCombo"] and bool(cats & DRINK_CATEGORIES)
        heavy = [_heavy(x["code"], x.get("mods", [])) for x in parts]
        variants = [("standard", [[] for _ in parts])] + ([("light", heavy)] if any(heavy) else [])
        for variant, removed in variants:
            t = combo_nutrition([{"code": x["code"], "name": x["name"], "removed": [m["code"] for m in r]}
                                 for x, r in zip(parts, removed)])
            if t.missing:
                break
            out.append(Option(
                p["code"], p["name"], variant,
                tuple((x["code"], m["code"]) for x, r in zip(parts, removed) for m in r),
                tuple(m["name"] for r in removed for m in r),
                p["priceFen"], p.get("gold"), t.kcal, t.low, t.high, t.protein, t.confidence, is_main, is_drink,
                p["isCombo"]))
    return out


def _bundle(opts) -> Bundle:
    return Bundle(opts, sum(o.price_fen for o in opts), sum(o.kcal for o in opts), sum(o.low for o in opts),
                  sum(o.high for o in opts), sum(o.protein for o in opts),
                  min((o.confidence for o in opts), key=CONF_RANK.get))


def build_bundles(options, max_items=3):
    out = []
    for k in range(1, max_items + 1):
        for combo in combinations(options, k):
            if len({o.code for o in combo}) < k:
                continue
            mains = sum(o.is_main for o in combo)
            combos = sum(o.is_combo for o in combo)
            if not 1 <= mains <= 2 or sum(o.is_drink for o in combo) > 1 or combos > 1 or (combos and k > 2):
                continue
            out.append(_bundle(combo))
    return out


def _cheaper(a, b):
    return b is None or (a.price_fen, a.kcal) < (b.price_fen, b.kcal)


def _lighter(a, b):
    return b is None or (a.kcal, a.price_fen) < (b.kcal, b.price_fen)


def _stronger(a, b):
    return b is None or (a.protein, -a.price_fen, -a.kcal) > (b.protein, -b.price_fen, -b.kcal)


def pick(bundles, budget_fen, kcal_cap):
    best = {"cheapest": None, "lightest": None, "protein": None}
    for b in bundles:
        if b.price_fen <= budget_fen and b.kcal <= kcal_cap:
            _update(best, b)
    return best if best["cheapest"] else {}


def _update(best, b):
    if _cheaper(b, best["cheapest"]):
        best["cheapest"] = b
    if _lighter(b, best["lightest"]):
        best["lightest"] = b
    if _stronger(b, best["protein"]):
        best["protein"] = b


def recommend_grid(bundles, budgets=BUDGETS, caps=KCAL_CAPS):
    by_price = sorted(bundles, key=lambda b: b.price_fen)
    grid = {}
    for cap in caps:
        pool = [b for b in by_price if b.kcal <= cap]
        best = {"cheapest": None, "lightest": None, "protein": None}
        i = 0
        for budget in budgets:
            while i < len(pool) and pool[i].price_fen <= budget:
                _update(best, pool[i])
                i += 1
            grid[(budget, cap)] = dict(best) if best["cheapest"] else {}
    return grid
```

- [ ] **Step 4: 运行测试通过**

Run: `.venv/bin/python -m pytest tests/test_recommend.py -q`
Expected: `5 passed`

- [ ] **Step 5: 提交**

```bash
git add skill/mcd-lean-maker/scripts/mcdcalc/recommend.py tests/test_recommend.py
git commit -m "feat: 预算与热量双约束下推荐最省钱、最低卡、高蛋白三套点法

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 7: 门店快照采集

**Files:**
- Create: `tools/snapshot.py`, `web/snapshot/products.json`, `web/snapshot/meta.json`(运行生成)
- Modify: `tests/fixtures/modification-options.raw.json`(运行时同步)
- Delete: `data/products.raw.json`, `scripts/collect_modifications.py`
- Test: `tests/test_snapshot.py`

**Interfaces:**
- Consumes: `mcp_client.call`, `mcdcalc.offers.yuan_to_fen`
- Produces(纯函数,可测):`removable_mods(modification: dict|None) -> list[{"code","name"}]`(只保留有 `unselectedKey` 的值;冰量、甜度组没有)、`diff_fen(text: str) -> int`(`"+ ¥1.5"`→150,`"- ¥0.5"`→-50)、`base_price_fen(meal: dict) -> int`(`discountType=="随单购麦金卡优惠"` 时取 `originalPrice`,否则 `currentPrice`)、`parse_gold(code: str, price_data: dict) -> {"priceFen","feeFen"}`、`normalize_product(code, meal, detail, categories, tags, gold) -> dict`(输出 Task 6 的商品快照结构,另加 `image`、`isNew = any("上新" in t for t in tags)`)
- 快照不含券、会员、订单、traceId

- [ ] **Step 1: 写失败测试 `tests/test_snapshot.py`**

```python
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
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_snapshot.py -q`
Expected: FAIL,`ModuleNotFoundError: No module named 'snapshot'`

- [ ] **Step 3: 实现 `tools/snapshot.py`**

```python
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
```

- [ ] **Step 4: 运行测试通过**

Run: `.venv/bin/python -m pytest tests/test_snapshot.py -q`
Expected: `5 passed`

- [ ] **Step 5: 采集快照(维护者本地,需 Token)**

```bash
export MCD_MCP_TOKEN=<你的 Token>
.venv/bin/python -c "import sys; sys.path[:0]=['tools','skill/mcd-lean-maker/scripts']; import snapshot; sys.argv=['snapshot']; snapshot.main()"
.venv/bin/python -m pytest -q
```

Expected: 打印 `products≈117 mods≈23`;全量测试 PASS。若 `test_every_collected_option_has_calories` 失败,说明出现新特制项:按 spec 3.2 的方法(A/B/C)在 `modification-calories.json` 补齐后重跑。
检查快照无个人数据:`grep -cE "couponCode|memberId|orderId|traceId" web/snapshot/*.json` 应输出 0。

- [ ] **Step 6: 删除旧采集产物并提交**

```bash
git rm -q data/products.raw.json scripts/collect_modifications.py
git add tools/snapshot.py tests/test_snapshot.py tests/fixtures web/snapshot
git commit -m "feat: 门店菜单、特制项与麦金卡价快照采集

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 8: 演示页预计算构建

**Files:**
- Create: `tools/build_web.py`
- Test: `tests/test_build_web.py`

**Interfaces:**
- Consumes: `web/snapshot/products.json`、`meta.json`;`item_nutrition`、`mod_delta`、`build_options`、`build_bundles`、`recommend_grid`、`BUDGETS`、`KCAL_CAPS`、`quote`
- Produces(`build(out_dir: Path) -> dict[str,int]`,返回各文件字节数):
  - `items.json`:`{code: {"name","image","categories","isNew","isCombo","priceFen","originalFen","gold","mods":[{"code","name","kcal","range","confidence"}],"results":{mask: {"kcal","low","high","protein","fat","carbohydrate","sodium","confidence","adjusted"}}|null,"rounds":[{"name","choices":[{"code","isDefault","diffFen"}]}]}}`。mask 为字符串形式的整数,第 i 位 = 去掉 `mods[i]`;`results` 为 null 表示无营养数据。套餐子项的 choice code 也作为独立条目写入
  - `recommend.json`:`{"budgets":[...],"caps":[...],"bundles":[{"items":[{"code","name","variant","removed":[名称]}],"priceFen","gold":{"goldFen","verdict"}|null,"kcal","low","high","protein","confidence"}],"grid":{"<budget>_<cap>":[cheapestIdx,lightestIdx,proteinIdx]|[]}}`;bundles 去重,grid 存下标
  - `meta.json`:快照 meta + `{"builtAt","budgets":[min,max,step],"caps":[min,max,step],"confidenceNote":"官方=营养表原值;高/中/低=特制项或新品估算"}`
  - 三个文件总字节 ≤ 3_000_000,超出时抛 `SystemExit`

- [ ] **Step 1: 写失败测试 `tests/test_build_web.py`**

```python
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
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_build_web.py -q`
Expected: FAIL,`ModuleNotFoundError: No module named 'build_web'`

- [ ] **Step 3: 实现 `tools/build_web.py`**

```python
"""Precompute everything the static demo page needs into web/data."""
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

from mcdcalc.nutrition import item_nutrition, mod_delta
from mcdcalc.offers import quote
from mcdcalc.recommend import BUDGETS, KCAL_CAPS, build_bundles, build_options, recommend_grid

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "web" / "snapshot"
MAX_BYTES = 3_000_000
RESULT_KEYS = ("kcal", "low", "high", "protein", "fat", "carbohydrate", "sodium", "confidence", "adjusted")


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
        out[str(mask)] = {k: n[k] for k in RESULT_KEYS}
    return out


def build_items(products):
    items = {}

    def add(code, name, mods, extra):
        if code not in items:
            items[code] = {"name": name, "mods": [_mod_info(code, m) for m in mods],
                           "results": _results(code, name, mods), **extra}

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
            "kcal": b.kcal, "low": b.low, "high": b.high, "protein": b.protein, "confidence": b.confidence}


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


def build(out_dir: Path) -> dict:
    products = json.loads((SNAP / "products.json").read_text(encoding="utf-8"))
    meta = json.loads((SNAP / "meta.json").read_text(encoding="utf-8"))
    meta.update({"builtAt": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M"),
                 "budgets": [BUDGETS.start, BUDGETS.stop - 1, BUDGETS.step],
                 "caps": [KCAL_CAPS.start, KCAL_CAPS.stop - 1, KCAL_CAPS.step],
                 "confidenceNote": "官方=营养表原值;高/中/低=特制项或新品估算"})
    out_dir.mkdir(parents=True, exist_ok=True)
    files = {"items.json": build_items(products), "recommend.json": build_recommend(products), "meta.json": meta}
    sizes = {}
    for name, obj in files.items():
        data = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
        (out_dir / name).write_text(data, encoding="utf-8")
        sizes[name] = len(data.encode())
    if sum(sizes.values()) > MAX_BYTES:
        raise SystemExit(f"web/data 超出 {MAX_BYTES} 字节: {sizes}")
    return sizes


if __name__ == "__main__":
    print(build(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "web" / "data"))
```

- [ ] **Step 4: 运行测试通过**

Run: `.venv/bin/python -m pytest tests/test_build_web.py -q`
Expected: `1 passed`。若超时(>120s)或超体积:先在 `build_options` 中对同一商品去掉被 light 版完全支配的 standard 版(light 价格相同、kcal 更低、蛋白不低于 standard 时删 standard),再重跑;仍超出则把 `BUDGETS` 步长改为 300 并同步 spec 4.1

- [ ] **Step 5: 本地生成并提交**

```bash
PYTHONPATH=skill/mcd-lean-maker/scripts:tools .venv/bin/python tools/build_web.py
git add tools/build_web.py tests/test_build_web.py
git commit -m "feat: 演示页去配料与推荐结果预计算

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 9: 演示页骨架与去配料计算器

**Files:**
- Create: `web/index.html`
- Test: 浏览器手动验证 + `tests/test_web_static.py`

**Interfaces:**
- Consumes: `web/data/items.json`、`meta.json`(Task 8 结构)
- 页面 JS 约定(Task 10 继续使用):全局 `state = {items, rec, meta, current: {code, mask, choices:{roundIdx: code}, choiceMasks:{roundIdx: mask}}}`;`fen(n) -> "¥25.5"`;`resultOf(code, mask) -> result|null`;`comboTotal() -> {kcal, low, high, protein, confidence, missing:[]}`

先加载设计 skill:在执行本任务前调用 Skill `frontend-design`(项目级已安装),按其指引定视觉细节;下列 token 与结构为硬约束。

- [ ] **Step 1: 写静态约束测试 `tests/test_web_static.py`**

```python
import re
from pathlib import Path

HTML = (Path(__file__).resolve().parents[1] / "web" / "index.html").read_text(encoding="utf-8")


def test_no_external_assets_except_menu_images():
    urls = re.findall(r'(?:src|href)=["\'](https?://[^"\']+)', HTML)
    assert urls == [], urls
    assert "fonts.googleapis" not in HTML and "cdn." not in HTML


def test_brand_tokens_and_disclaimer():
    assert "#DA291C" in HTML and "#FFC72C" in HTML
    assert "非官方" in HTML and "基于麦当劳 MCP" in HTML


def test_sections_present():
    for sec in ('id="calc"', 'id="plan"', 'id="new"', 'id="share"', 'id="truth"'):
        assert sec in HTML, sec
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_web_static.py -q`
Expected: FAIL,`FileNotFoundError: .../web/index.html`

- [ ] **Step 3: 写 `web/index.html` 骨架**

结构(单文件,`<style>` 与 `<script>` 内联,`<html lang="zh-CN">`,viewport 适配手机):

```html
<header class="topbar">麦麦减脂助手 <small>非官方 · 基于麦当劳 MCP 的参赛作品</small></header>
<main>
  <section id="calc">  <!-- 去配料计算器 -->
    <div class="chips" id="cat-chips"></div>          <!-- 品类筛选 -->
    <div class="grid" id="product-grid"></div>        <!-- 商品卡:图、名、价、"上新"标签 -->
    <div class="panel" id="calc-panel" hidden>
      <h2 id="calc-name"></h2>
      <div id="calc-rounds"></div>                    <!-- 套餐:每轮 select;单品为空 -->
      <ul id="calc-mods"></ul>                        <!-- 配料开关:名称 + "−90 kcal(估)" -->
      <div class="kcal-bar"><b id="calc-kcal"></b><span id="calc-range"></span></div>
      <p id="calc-equiv"></p>                         <!-- "省下 136 kcal ≈ 1.5 个圆筒" -->
      <p id="calc-macro"></p>                         <!-- 蛋白/脂肪/碳水/钠;adjusted=false 时注"未扣除特制" -->
      <p id="calc-price"></p>                         <!-- 现价/原价/麦金卡净价与 verdict -->
    </div>
  </section>
  <section id="plan"></section>
  <section id="new"></section>
  <section id="share"></section>
  <section id="truth"></section>
</main>
<footer>非官方 · 基于麦当劳 MCP 的参赛作品 · 数据快照 <span id="snap-at"></span></footer>
```

CSS token(写在 `:root`):

```css
:root{--red:#DA291C;--yellow:#FFC72C;--ink:#27251F;--muted:#6F6F6F;--bg:#F7F7F7;--card:#FFFFFF;
  --radius:16px;--shadow:0 2px 10px rgba(0,0,0,.08);
  font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;}
body{margin:0;background:var(--bg);color:var(--ink);}
.topbar{background:var(--red);color:#fff;font-weight:800;padding:14px 16px;position:sticky;top:0;}
.btn-primary{background:var(--yellow);color:var(--ink);border:0;border-radius:999px;font-weight:700;padding:12px 20px;}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px;}
```

核心 JS(内联 `<script>`):

```js
const state = {items:null, rec:null, meta:null, current:null};
const fen = n => '¥' + (n/100).toFixed(2).replace(/\.?0+$/, '');
const EQUIV = [['圆筒冰淇淋',93],['小薯条',210],['可乐中杯',147]];

async function boot(){
  const [items, rec, meta] = await Promise.all(['items','recommend','meta']
    .map(n => fetch(`data/${n}.json`).then(r => r.json())));
  Object.assign(state, {items, rec, meta});
  document.getElementById('snap-at').textContent = `${meta.storeName} ${meta.snapshotAt}`;
  renderChips(); renderGrid(); renderPlan(); renderNew(); renderTruth();
}

function resultOf(code, mask){ const it = state.items[code]; return it && it.results ? it.results[String(mask)] : null; }

function comboTotal(){
  const c = state.current, it = state.items[c.code];
  const parts = it.isCombo
    ? it.rounds.map((r, i) => [c.choices[i], c.choiceMasks[i] || 0])
    : [[c.code, c.mask]];
  const t = {kcal:0, low:0, high:0, protein:0, confidence:'官方', missing:[], adjusted:true};
  const rank = {'官方':3,'高':2,'中':1,'低':0};
  for (const [code, mask] of parts){
    const r = resultOf(code, mask);
    if (!r){ t.missing.push(state.items[code]?.name || code); continue; }
    for (const k of ['kcal','low','high','protein']) t[k] += r[k];
    if (rank[r.confidence] < rank[t.confidence]) t.confidence = r.confidence;
    t.adjusted = t.adjusted && r.adjusted;
  }
  return t;
}

function equivText(saved){
  if (saved < 30) return '';
  const [name, k] = EQUIV.find(([, k]) => saved >= k * 0.8) || EQUIV[0];
  return `省下 ${Math.round(saved)} kcal ≈ ${(saved / k).toFixed(1)} 份${name}`;
}
```

`renderGrid` 只列 `!item.choiceOnly` 的商品;点击商品后设置 `state.current = {code, mask:0, choices:{默认选项}, choiceMasks:{}}` 并调用 `renderCalc()`。`renderCalc` 根据单品/套餐渲染开关与 select,每次变化重算 `comboTotal()`,并以 `mask=0` 的结果作为基线计算 `saved`。套餐换 choice 时把 `diffFen` 计入价格。`results` 为 null 时整块显示"暂无营养数据"。低置信项开关后缀"(估)"。

- [ ] **Step 4: 运行测试与本地预览**

```bash
.venv/bin/python -m pytest tests/test_web_static.py -q
PYTHONPATH=skill/mcd-lean-maker/scripts:tools .venv/bin/python tools/build_web.py
.venv/bin/python -m http.server 8000 -d web
```

Expected: 测试 `3 passed`。浏览器打开 `http://localhost:8000`:点巨无霸 → 关掉巨无霸酱与吉士 → 显示 `377 kcal(351–399)`;点任一套餐 → 换饮料后热量与价格同步变化;手机宽度(375px)无横向滚动

- [ ] **Step 5: 提交**

```bash
git add web/index.html tests/test_web_static.py
git commit -m "feat: 演示页去配料热量计算器

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 10: 演示页推荐、新品、分享卡、真实性说明

**Files:**
- Modify: `web/index.html`

**Interfaces:**
- Consumes: Task 9 的 `state`、`fen`、`comboTotal`;`recommend.json`(Task 8 结构)

- [ ] **Step 1: 推荐模块 `#plan`**

两个 `<input type="range">`:预算 `min=1000 max=8000 step=200`,热量 `min=200 max=1500 step=50`,默认 3000 / 700。变化时:

```js
function renderPlan(){
  const b = +budget.value, c = +cap.value;
  const idx = state.rec.grid[`${b}_${c}`] || [];
  const labels = ['最省钱','最低卡','高蛋白'];
  planCards.innerHTML = idx.length ? idx.map((i, n) => planCard(labels[n], state.rec.bundles[i])).join('')
    : '<p class="empty">这个预算和热量下找不到组合,试试放宽一点</p>';
}
```

`planCard` 显示:商品名列表(light 版附"去:巨无霸酱、吉士")、`fen(priceFen)`、有 gold 时显示麦金卡净价与 verdict、`kcal(low–high)`、蛋白、置信度角标。

- [ ] **Step 2: 新品模块 `#new`**

列出 `isNew && !choiceOnly` 的商品卡,热量取 `results["0"]`,置信度非"官方"时标"估算";点击跳到 `#calc` 并选中。

- [ ] **Step 3: 分享卡 `#share`**

按钮"生成我的减卡卡片",用当前计算器状态绘制 1080×1350 Canvas:红色顶栏 + 白卡;大字"{商品名} {基线kcal} → {当前kcal} kcal";小字"去掉:{名称列表}"、`equivText`、价格;底部"非官方 · 基于麦当劳 MCP"。导出:

```js
canvas.toBlob(b => { const a = document.createElement('a'); a.href = URL.createObjectURL(b);
  a.download = 'mcd-lean-maker.png'; a.click(); });
```

同时把图片以 `<img>` 显示在页面,方便手机长按保存。

- [ ] **Step 4: 真实性说明 `#truth`**

表格三行:"官方"=营养表原值(MCP list-nutrition-foods);"高/中/低"=特制项与新品估算,方法 A 营养表成对相减、B 海外官方数据校准、C 同类食材估算;价格=快照门店当时价格,实际以下单核价为准。附快照门店与时间、"想用实时数据和下单?看 Skill 安装"链接到仓库 README。

- [ ] **Step 5: 验证并提交**

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m http.server 8000 -d web
```

Expected: 全部测试 PASS;浏览器中拖动两个滑块,三张方案卡随档位变化,价格均 ≤ 预算、kcal ≤ 上限;分享卡能下载 PNG

```bash
git add web/index.html
git commit -m "feat: 演示页推荐方案、今日新品与分享卡

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 11: Skill CLI 与 SKILL.md

**Files:**
- Create: `skill/mcd-lean-maker/scripts/calc.py`, `skill/mcd-lean-maker/SKILL.md`, `skill/mcd-lean-maker/references/mcp-tools.md`, `skill/mcd-lean-maker/references/offers-rules.md`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `item_nutrition`、`combo_nutrition`、`mod_delta`、`quote`
- Produces CLI(stdin JSON → stdout JSON,UTF-8):
  - `calc.py nutrition`:输入 `{"parts":[{"code","name","removed":[modCode]}]}` → `{"kcal","low","high","protein","fat","carbohydrate","sodium","confidence","adjusted","missing"}`
  - `calc.py mods`:输入 `{"code","mods":[{"code","name"}]}` → `[{"code","name","kcal","range","confidence"}]`
  - `calc.py quote`:输入 `{"lines":[...]}`(Task 5 line 结构)→ `{"priceFen","originalFen","goldFen","goldFeeFen","verdict"}`
  - 输入错误时退出码 2,stderr 输出原因

- [ ] **Step 1: 写失败测试 `tests/test_cli.py`**

```python
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
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_cli.py -q`
Expected: FAIL(calc.py 不存在,returncode 2 且 stdout 为空导致断言失败)

- [ ] **Step 3: 实现 `scripts/calc.py`**

```python
"""mcd-lean-maker CLI: stdin JSON -> stdout JSON. Offline, no token."""
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
```

注:`test_bad_input_exit_2` 期望 stderr 含 "parts";`KeyError('parts')` 的 str 为 `'parts'`,满足。

- [ ] **Step 4: 写 `SKILL.md`**

```markdown
---
name: mcd-lean-maker
description: 麦当劳去配料热量与优惠计算(非官方)。当用户想知道麦当劳某个汉堡/套餐去掉酱、芝士、培根等配料后的热量,想在预算和热量限制下点麦当劳,想比较开麦金卡是否划算,或想找麦当劳今日新品并下单时使用。基于麦当劳中国 MCP 实时菜单、营养表与核价。
---

# 麦麦减脂助手

## 前置
- 需要已配置麦当劳 MCP(Token 来自 https://open.mcd.cn/mcp 控制台)。未配置时引导用户按 README 配置,不要索要或回显 Token。
- 计算统一调用 `scripts/calc.py`(离线、确定性)。金额以 `calculate-price` 返回为准。

## 主线
1. 选店:问城市+地点 → `query-nearby-stores`(searchType=2, beType=1)→ 用户选店
2. 推荐:`query-meals` 取 tags 含"上新"的商品;有需要时 `query-store-coupons`;可领券先问用户再 `auto-bind-coupons`
3. 选品去配料:`query-meal-detail` 取 modification;把用户说法("不要酱""去芝士")映射到 values 里有 unselectedKey 的项;
   `calc.py mods` 展示每项减多少 kcal;`calc.py nutrition` 给结果
4. 核价:`calculate-price`(特制项按规则传 selectedKey/unselectedKey;商品 canWithOrder 时再算一次带 withOrder 的价格)→ `calc.py quote` 给麦金卡结论
5. 确认卡:门店 · 商品与去掉的配料 · 热量(区间、估算标注)· 券 · 实付 · 取餐方式(takeWayList)
6. 下单:见安全规则 → `create-order` → 引导 App 支付 → 用户回复后 `query-order`

## 展示规则
- 热量写"约 377 kcal(351–399)";置信度非"官方"加"估";`adjusted=false` 注"蛋白等未扣除特制"
- `missing` 非空时列出"暂无营养数据"的商品,不猜
- 麦金卡只展示 verdict,不代用户开卡

## 安全规则
- 只有用户明确说"确认下单/下单"才调 `create-order`;"试试""可以吧"不算
- 确认后用户改任何内容 → 重新 `calculate-price`、重新出确认卡、重新确认
- 一次确认只创建一单;支付由用户在 App 完成
- 领券、开卡都要先征得同意

详见 `references/mcp-tools.md`、`references/offers-rules.md`。
```

- [ ] **Step 5: 写两个 references**

`references/mcp-tools.md`:表格列出 `query-nearby-stores`、`query-meals`、`query-meal-detail`、`query-store-coupons`、`available-coupons`、`auto-bind-coupons`、`calculate-price`、`create-order`、`query-order`、`cancel-order`,每行写用途、必填参数、易错点(到店不传 beCode;modification 组内所有项都要传,选中用 selectedKey、未选用 unselectedKey;价格单位为分;`takeWayCode` 来自 `calculate-price.takeWayList`)。

`references/offers-rules.md`:每单只能用一张券、多券需拆单;门店维度可用券以 `query-store-coupons` 为准;菜单 `discountType=随单购麦金卡优惠` 时 currentPrice 是开卡后价格;麦金卡净价 = 随单购价 + 卡费,卡费一单只算一次(2026-10-14 实测:麦辣鸡腿堡四件套 ¥57 → ¥28 + 月卡 ¥19 = ¥47)。

- [ ] **Step 6: 运行测试并提交**

Run: `.venv/bin/python -m pytest -q`
Expected: 全部 PASS

```bash
git add skill/mcd-lean-maker tests/test_cli.py
git commit -m "feat: Skill 命令行计算入口与点餐流程说明

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 12: CI、部署配置与参赛文档

**Files:**
- Create: `.github/workflows/pages.yml`, `netlify.toml`, `README.md`, `MCP_INTEGRATION.md`, `CONTEST_DECLARATION.md`, `mcp-config.example.json`, `LICENSE`

- [ ] **Step 1: `.github/workflows/pages.yml`**

```yaml
name: test-and-deploy
on:
  push:
    branches: [master]
  pull_request:
permissions:
  contents: read
  pages: write
  id-token: write
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install pytest==8.3.3
      - run: python -m pytest -q
      - run: PYTHONPATH=skill/mcd-lean-maker/scripts:tools python tools/build_web.py
      - uses: actions/upload-pages-artifact@v3
        with:
          path: web
  deploy:
    if: github.event_name == 'push'
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

- [ ] **Step 2: `netlify.toml`**

```toml
[build]
  command = "PYTHONPATH=skill/mcd-lean-maker/scripts:tools python3 tools/build_web.py"
  publish = "web"
```

- [ ] **Step 3: `mcp-config.example.json`**

```json
{
  "mcpServers": {
    "mcd-mcp": {
      "type": "streamablehttp",
      "url": "https://mcp.mcd.cn",
      "headers": { "Authorization": "Bearer ${MCD_MCP_TOKEN}" }
    }
  }
}
```

- [ ] **Step 4: `CONTEST_DECLARATION.md` 原样复制官方文件**

```bash
curl -fsSL https://raw.githubusercontent.com/M-China/mcd-developer-innovation-challenge/HEAD/CONTEST_DECLARATION.md -o CONTEST_DECLARATION.md
```

内容不得修改。

- [ ] **Step 5: `MCP_INTEGRATION.md`**

章节:使用的 MCP Server(`https://mcp.mcd.cn`,streamablehttp)→ 工具清单表(工具、调用阶段、用途、业务价值,覆盖 Task 11 references 中的 10 个工具 + `list-nutrition-foods`)→ 调用流程(选店 → 菜单/新品 → 详情/特制 → 本地计算 → 核价 → 确认 → 下单)→ 演示页数据流(维护者本地 snapshot → build_web 预计算 → Pages,不含 Token)→ 业务价值(配料级热量、麦金卡真实净价)。

- [ ] **Step 6: `README.md`**

章节顺序:
1. 标题"麦麦减脂助手"+ 一句话"去掉酱、芝士、培根各少多少卡,怎么点最省钱,一页算清" + 在线体验链接(Pages 主站 / Netlify 镜像)+ 首屏截图 `docs/preview.png`
2. 亮点:配料级热量(23 个特制项,每项带区间与置信度)· 预算×热量三套方案 · 麦金卡真实净价 · 今日新品 · 分享卡
3. 和别人有什么不一样(一句话:榜单上能"去酱"的项目只传参不算热量;本项目量化每一项)
4. 给普通用户:打开链接即用
5. 给开发者:安装 Skill(复制 `skill/mcd-lean-maker` 到 `~/.claude/skills/` 或 WorkBuddy 技能目录;按 `mcp-config.example.json` 配 MCP,Token 用环境变量)+ 使用示例对话
6. 数据真实性对照表(官方 / 估算 A/B/C / 快照价格)
7. 开发:`pytest`、`snapshot.py`、`build_web.py`
8. 非官方声明 + 参赛声明链接

- [ ] **Step 7: LICENSE(MIT)并提交**

```bash
git add .github netlify.toml README.md MCP_INTEGRATION.md CONTEST_DECLARATION.md mcp-config.example.json LICENSE
git commit -m "docs: 参赛文档、MCP 说明与自动部署配置

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 13: UI 审查、截图与发布(需用户参与)

**Files:**
- Modify: `web/index.html`(按审查结果)
- Create: `docs/preview.png`

- [ ] **Step 1: UI 审查**

调用 Skill `web-design-guidelines` 审查 `web/index.html`,逐条修复可访问性问题(对比度、按钮可聚焦、`aria-label`、开关用 `<input type="checkbox">`+`<label>`、375px 宽度无横向滚动)。修复后重跑 `.venv/bin/python -m pytest -q`。

- [ ] **Step 2: 截图**

本地 `http.server` 打开页面,选巨无霸去酱去芝士,截取首屏保存为 `docs/preview.png`(宽 1200 左右)。

- [ ] **Step 3: 提交**

```bash
git add web/index.html docs/preview.png
git commit -m "fix: 演示页可访问性与移动端适配

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 4: 发布(以下每步执行前向用户确认)**

1. 用户在 GitHub 新建公开仓库 `mcd-lean-maker`;本地 `git remote add origin ...`
2. 合并特性分支到 master 后 `git push -u origin master`(推送是公开动作,需用户确认)
3. 仓库 Settings → Pages → Source 选 "GitHub Actions";等待 workflow 成功,访问 `https://farsightli.github.io/mcd-lean-maker/`
4. Netlify:用 GitHub 登录 → Import 该仓库 → 使用 `netlify.toml` 默认设置部署,得到 `*.netlify.app`
5. 把两个链接填回 README 并提交推送
6. 在 `M-China/mcd-developer-innovation-challenge` 提报名 Issue(标题与正文之间不换行,项目地址不用 Markdown 链接),内容由用户确认后提交:

```text
【参赛申请】
项目名称：mcd-lean-maker 麦麦减脂助手
项目地址：https://github.com/FarSightLi/mcd-lean-maker
项目简介：去掉酱、芝士、培根各少多少卡，预算和热量限制下怎么点最省钱，一页算清
```

---

## 追加任务(spec §10–11,2026-10-14)

### Task 14: 推荐计入麦金卡净价 + 构建入口拆分

**Files:**
- Modify: `skill/mcd-lean-maker/scripts/mcdcalc/recommend.py`, `tools/build_web.py`, `tests/test_recommend.py`, `tests/test_build_web.py`

**Interfaces:**
- `Bundle` 增加字段 `best_fen: int`、`needs_gold: bool`、`gold_fen: int | None`(开卡净价,含卡费)、`gold_fee_fen: int`
  - `gold_fen` = Σ(有 gold 的 option 用 `gold["priceFen"]`,否则 `price_fen`) + max(各 option `gold["feeFen"]`);无 gold 时为 None、fee 为 0
  - `best_fen = min(price_fen, gold_fen)`;`needs_gold = gold_fen is not None and gold_fen < price_fen`
- `pick` / `recommend_grid` 预算过滤与排序改用 `best_fen`:cheapest (best_fen, kcal);lightest (kcal, best_fen);protein (protein, −best_fen, −kcal);grid 按 best_fen 排序扫描
- `tools/build_web.py` 新增 `build_payload(products: list, meta: dict) -> dict[str, object]`(返回 `{"items.json":…, "recommend.json":…, "meta.json":…}`),`build(out_dir)` 读快照后调用它再写文件
- recommend.json 每个 bundle 增加 `"bestFen"`、`"needsGold"`、`"goldFeeFen"`;保留原 `priceFen` 与 `gold`

- [ ] **Step 1: 写失败测试**(追加到 `tests/test_recommend.py`)

```python
def test_gold_card_net_price_used_for_ranking():
    bigmac = {**BIGMAC, "gold": {"priceFen": 500, "feeFen": 1900}}
    cola = {**COLA, "gold": {"priceFen": 500, "feeFen": 1900}}
    bundles = build_bundles(build_options([bigmac, HAMBURGER, FRIES, cola]))
    solo = next(b for b in bundles if [(o.code, o.variant) for o in b.options] == [("1100", "standard")])
    assert (solo.price_fen, solo.gold_fen, solo.best_fen, solo.needs_gold) == (2550, 2400, 2400, True)
    pair = next(b for b in bundles if {o.code for o in b.options} == {"1100", "3050"} and all(o.variant == "standard" for o in b.options))
    assert pair.gold_fen == 500 + 500 + 1900 and pair.gold_fee_fen == 1900   # 卡费一单一次
    plans = pick(bundles, 2450, 600)
    assert plans["protein"].best_fen <= 2450 and plans["protein"].needs_gold


def test_no_gold_bundle_fields():
    b = build_bundles(build_options([HAMBURGER]))[0]
    assert (b.gold_fen, b.gold_fee_fen, b.best_fen, b.needs_gold) == (None, 0, 1200, False)
```

`tests/test_build_web.py` 中 `cheapest["priceFen"] <= 3000` 改为 `cheapest["bestFen"] <= 3000`,并追加:

```python
    assert all({"bestFen", "needsGold", "goldFeeFen"} <= set(b) for b in rec["bundles"])
```

- [ ] **Step 2: 运行确认失败** — `.venv/bin/python -m pytest tests/test_recommend.py tests/test_build_web.py -q`,Expected: `AttributeError: 'Bundle' object has no attribute 'gold_fen'`

- [ ] **Step 3: 实现**(recommend.py `_bundle` 与比较函数,build_web.py `build_payload` 与 `_bundle_json`)

```python
def _bundle(opts) -> Bundle:
    price = sum(o.price_fen for o in opts)
    golds = [o.gold for o in opts if o.gold]
    fee = max((g["feeFen"] for g in golds), default=0)
    gold = sum(o.gold["priceFen"] if o.gold else o.price_fen for o in opts) + fee if golds else None
    best = min(price, gold) if gold is not None else price
    return Bundle(opts, price, sum(o.kcal for o in opts), sum(o.low for o in opts), sum(o.high for o in opts),
                  sum(o.protein for o in opts), min((o.confidence for o in opts), key=CONF_RANK.get),
                  best, gold is not None and gold < price, gold, fee)
```

`Bundle` 新字段顺序:`options, price_fen, kcal, low, high, protein, confidence, best_fen, needs_gold, gold_fen, gold_fee_fen`。比较函数与 `pick`/`recommend_grid` 中的 `price_fen` 全部换成 `best_fen`。`_bundle_json` 直接用 bundle 字段输出 `bestFen/needsGold/goldFeeFen`,`gold` 保留 `{"goldFen","verdict"}`(verdict 用 `offers.quote` 生成)。

- [ ] **Step 4: 全量测试、重建** — `.venv/bin/python -m pytest -q` 全部 PASS;`PYTHONPATH=skill/mcd-lean-maker/scripts:tools .venv/bin/python tools/build_web.py`,报告含 needsGold 的方案数

- [ ] **Step 5: 提交** — `feat: 推荐按开卡净价与不开卡价中较低者排序`

### Task 15: 本地实时模式服务

**Files:**
- Modify: `tools/snapshot.py`(抽出 `collect`)
- Create: `tools/serve.py`, `tests/test_serve.py`

**Interfaces:**
- `snapshot.collect(store: str, store_name: str, call=call) -> tuple[list, dict]`:返回 (products, meta),不写文件;`main()` 调用它再写快照与 fixture
- `serve.LiveState(collect=snapshot.collect, search=search_stores)`:`load(store, name) -> meta`(10 分钟缓存,线程锁),`current: dict|None`(最近加载的 payload)
- `serve.search_stores(city, keyword) -> [{"storeCode","storeName","address"}]`
- `serve.make_handler(state)` 路由见 spec §10;异常返回 `{"error": ...}`(400 缺参数 / 502 MCP 失败),不含 Token
- `serve.main()`:无 `MCD_MCP_TOKEN` 时退出;`ThreadingHTTPServer(("127.0.0.1", port))`,默认端口 8000

- [ ] **Step 1: 写失败测试 `tests/test_serve.py`**

```python
import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from serve import LiveState, make_handler

SNAP = Path(__file__).resolve().parents[1] / "web" / "snapshot"
PRODUCTS = json.loads((SNAP / "products.json").read_text(encoding="utf-8"))


def fake_collect(store, name):
    return PRODUCTS, {"storeCode": store, "storeName": name, "productCount": len(PRODUCTS), "snapshotAt": "now"}


def fake_search(city, keyword):
    return [{"storeCode": "1", "storeName": f"{city}{keyword}店", "address": "x"}]


def serve():
    state = LiveState(collect=fake_collect, search=fake_search)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(state))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, state


def get(srv, path):
    with urllib.request.urlopen(f"http://127.0.0.1:{srv.server_address[1]}{path}") as r:
        return json.loads(r.read())


def test_live_routes():
    srv, state = serve()
    try:
        assert srv.server_address[0] == "127.0.0.1"
        assert get(srv, "/api/ping") == {"live": True}
        assert get(srv, "/api/stores?city=北京&keyword=国贸")[0]["storeName"] == "北京国贸店"
        meta = get(srv, "/api/load?store=1&name=测试店")
        assert meta["storeName"] == "测试店"
        assert get(srv, "/data/meta.json")["storeName"] == "测试店"
        assert "1100" in get(srv, "/data/items.json")
    finally:
        srv.shutdown()


def test_cache_reuses_payload():
    calls = []
    state = LiveState(collect=lambda s, n: (calls.append(s), fake_collect(s, n))[1], search=fake_search)
    state.load("1", "a")
    state.load("1", "a")
    assert calls == ["1"]


def test_missing_param_400():
    srv, _ = serve()
    try:
        try:
            get(srv, "/api/load")
            raise AssertionError("expected 400")
        except urllib.error.HTTPError as e:
            assert e.code == 400 and "error" in json.loads(e.read())
    finally:
        srv.shutdown()
```

- [ ] **Step 2: 运行确认失败** — Expected: `ModuleNotFoundError: No module named 'serve'`

- [ ] **Step 3: 实现** — 按 Interfaces;`serve.py` 用 `SimpleHTTPRequestHandler(directory=web/)`,重写 `log_message` 为空,`/data/<name>.json` 在 `state.current` 有该键时返回实时数据,否则交给静态文件;`/api/load` 调 `state.load` 后返回 meta;payload 由 `build_web.build_payload(products, meta)` 生成

- [ ] **Step 4: 测试通过并手动验证** — `.venv/bin/python -m pytest -q` 全部 PASS;用本机 Token 启动 `PYTHONPATH=skill/mcd-lean-maker/scripts:tools .venv/bin/python tools/serve.py --port 8770`(后台),curl `api/stores?city=北京市&keyword=国贸` 与 `api/load?store=1950564&name=测试`(记录耗时),确认 `curl http://<局域网IP>:8770/` 连接被拒,结束进程

- [ ] **Step 5: 提交** — `feat: 本地实时模式服务,用自有 Token 拉取门店数据`

### Task 16: 前端实时模式与开卡净价展示

**Files:**
- Modify: `web/index.html`, `tests/test_web_static.py`, `README.md`

- [ ] **Step 1: 静态测试追加**

```python
def test_live_mode_hooks():
    assert 'id="live-bar"' in HTML and "api/ping" in HTML and "api/load" in HTML
```

- [ ] **Step 2: 实现**
  - 顶部 `#live-bar` 默认 `hidden`;`boot()` 先 `fetch('api/ping')`,成功则显示:城市输入 + 地点输入 + "搜索门店"按钮 → `api/stores` 列表 → 点门店 → 显示"正在拉取门店菜单(约 30–60 秒)…" → `api/load?store=&name=` → 重新 fetch 三个 data JSON 并重新渲染全部模块;失败显示接口返回的 `error`
  - 页脚/真实性说明:实时模式显示"实时 · {门店} · {时间}",静态模式显示"快照 · {门店} · {时间}"
  - 推荐方案卡:价格显示 `bestFen`;`needsGold` 时加标签"需开卡(含卡费 {fen(goldFeeFen)})",并在小字显示不开卡价 `priceFen`
  - README 增加"本地实时模式"一节:`export MCD_MCP_TOKEN=...` → `PYTHONPATH=skill/mcd-lean-maker/scripts:tools python3 tools/serve.py` → 打开 `http://127.0.0.1:8000/`;说明仅本机可访问、网页不下单、下单用 Skill

- [ ] **Step 3: 验证** — 全量测试 PASS;静态模式(`http.server`)下 `#live-bar` 不显示;实时模式(`serve.py`)下截图确认门店搜索栏出现

- [ ] **Step 4: 提交** — `feat: 演示页支持本地实时门店数据与开卡净价方案`
