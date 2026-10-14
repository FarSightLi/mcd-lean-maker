# mcd-lite-calc 麦麦减卡计算器 设计

日期:2026-10-14 · 比赛截止:2026-10-25 23:59

## 1. 目标

基于麦当劳中国 MCP,做一个"去配料热量 + 优惠"计算工具,分两部分:

| 部分 | 用户 | 数据 | 能力 |
|---|---|---|---|
| 演示页 | 非技术人员 | 一家样例门店的脱敏快照 | 去配料热量、预算×热量推荐、今日新品、分享卡。无需 Token,不能下单 |
| Skill | 技术人员 | MCP 实时数据,用户自配 Token | 演示页全部能力 + 选店、领券、核价、确认后下单 |

差异化:榜单 105 个项目中,mcd-calorie-butler、mcd-baby-bite 能把去酱转成下单参数,但无项目量化"每个特制项减多少 kcal"(见 `docs/research/leaderboard-summary.md`)。本项目以配料级热量为主卖点,优惠为第二维度,下单功能保留但不在演示页出现。

## 2. 架构

计算逻辑只有一份 Python 实现。演示页不做计算,只查预计算 JSON。

```
mcd-lite-calc/
├── core/
│   ├── data/
│   │   ├── nutrition.json              list-nutrition-foods 160 条快照
│   │   ├── modification-calories.json  特制项热量增减(23 项,含区间/置信度/来源)
│   │   ├── aliases.json                productCode → 营养表名称
│   │   └── derived-nutrition.json      营养表外商品(新品)的推导值
│   └── mcdcalc/                        Python 包,纯函数,不联网
│       ├── nutrition.py                单品/套餐营养 + 去配料重算
│       ├── offers.py                   券归类、每单一券、麦金卡净额
│       └── recommend.py                预算×热量约束下的方案搜索
├── skill/mcd-lite-calc/
│   ├── SKILL.md
│   ├── references/mcp-tools.md · offers-rules.md
│   └── scripts/calc.py                 CLI 入口:stdin JSON → stdout JSON,调用 mcdcalc
├── tools/
│   ├── snapshot.py                     本地运行:拉 MCP 数据,脱敏,写 web/snapshot/
│   └── build_web.py                    读快照,调 mcdcalc 预计算,写 web/data/*.json
├── web/
│   ├── index.html                      单文件,无外部 CDN/字体
│   ├── snapshot/                       脱敏快照(入库)
│   └── data/                           预计算结果(CI 生成,不入库)
├── tests/                              pytest
├── .github/workflows/pages.yml         test → build_web → 部署 GitHub Pages
└── README.md · MCP_INTEGRATION.md · CONTEST_DECLARATION.md · mcp-config.example.json
```

依赖方向:`skill/scripts` 和 `tools/` 依赖 `core/mcdcalc`;`mcdcalc` 只依赖 `core/data` 与 Python 标准库。

## 3. 计算口径

### 3.1 营养匹配
按顺序,命中即停:
1. `aliases.json` 按 productCode 查
2. 营养表名称精确匹配(NFKC 归一化、去空格)
3. `derived-nutrition.json`
4. 标记 `unmatched`,展示"暂无营养数据",不估算

禁止模糊匹配。"双层/单层""大/中/小杯"属不同商品。

### 3.2 去配料
- 热量 = 整品 kcal − Σ 被去除项 kcal;区间端点分别累加
- 商品级 `overrides` 优先于通用值(如 1120 双层吉士去吉士 −92)
- 蛋白/脂肪/碳水/钠:被去除项有 `nutrients` 字段才扣减,否则保留整品值并标 `nutrientsAdjusted=false`
- 置信度取被去除项中最低者
- `nonCaloric`(冰量)不影响热量;甜度选项提示"未计入"

### 3.3 套餐
按 rounds 子项分别计算后相加。换搭配时按换后的 choice code 重新匹配。任一子项 unmatched,整单标"部分缺数据"并列出缺失项。

### 3.4 优惠
- 券来源:Skill 用 `query-store-coupons`(门店维度),快照同口径
- 券归类:单品改价 / 折扣 / 满减 / 组合价 / 赠品;无法判定的忽略
- 每单最多一张券;多张券需拆单,给出拆单方案
- 麦金卡:净价 = 随单购后总价 + 开卡费;仅当净价低于不开卡时提示"开卡划算",否则提示"开卡更贵"
- 金额以分为单位的整数计算
- Skill 中最终金额以 `calculate-price` 返回为准,本地计算仅用于排序与演示

### 3.5 推荐
- 输入:预算(分)、热量上限(kcal)、可选"必含品类"
- 候选:快照内有营养数据的单品与套餐,每份可附加去配料方案
- 输出三套:最省钱、最低卡、性价比(kcal 满足下单价最低,同价取蛋白高)
- 搜索:单品 1–3 件组合全枚举 + 套餐;去配料按"减卡/不影响口味"优先级只取前 2 种方案,控制组合规模

## 4. 演示页

### 4.1 档位
| 滑块 | 范围 | 步长 | 档数 |
|---|---|---|---|
| 预算 | ¥10–¥80 | ¥2 | 36 |
| 热量上限 | 200–1500 kcal | 50 kcal | 27 |

共 972 组,每组存前 3 方案。若 `web/data` 总量 > 3MB,先压缩字段再考虑放宽步长。

### 4.2 模块(单页滚动)
1. 去配料计算器:选商品 → 配料开关 → 热量"513 → 377 kcal(352–402)"+ 等价换算(如"≈1 个圆筒")。套餐可展开子项
2. 怎么点最划算:两个滑块 → 三套方案卡(价格:原价/券后/麦金卡净价;热量;去配料建议)
3. 今日新品:快照中 tags 含"上新"的商品,营养标"估算"
4. 分享卡:Canvas 生成 PNG,可下载/长按保存

页脚:真实性对照表(官方/估算字段、快照日期、门店)、Skill 安装入口。

### 4.3 页面 JS 职责
仅限:加载 JSON、响应交互、查表、绘制分享卡。不含任何计算规则。

### 4.4 预计算数据
- `items.json`:每个商品的全部配料开关组合(≤2^n,n≤5)→ 营养结果
- `combos.json`:套餐每个子项的上述结果,前端按子项选择相加
- `recommend.json`:972 组档位 → 前 3 方案
- `new.json`、`meta.json`(快照日期、门店名、数据说明)

套餐子项相加属于展示层求和,不涉及口径规则,允许在前端完成。

## 5. Skill 主线

1. 选店:`query-nearby-stores`,用户选
2. 推荐:`query-meals`(新品)+ `query-store-coupons` + 可领券提示(领取前征得同意,`auto-bind-coupons`),经 `calc.py` 附营养
3. 选品去配料:`query-meal-detail` 把用户说法映射为 modification code → `calc.py` 重算
4. 核价:`calculate-price`(含券、可选随单购),`calc.py` 对比开卡与否
5. 确认卡:门店、商品与特制、热量区间、券、实付、取餐方式
6. 下单:用户明确"确认下单"后 `create-order`,引导 App 支付,`query-order` 查状态

### 安全规则
- Token 仅来自平台 MCP 连接器或环境变量 `MCD_MCP_TOKEN`;仓库只有 `mcp-config.example.json` 占位
- "试试看""可以吧"不算确认;任何改动后重新核价、重出确认卡;一次确认一单
- 领券、开卡均需征得同意;麦金卡只测算不代买
- `snapshot.py` 只在维护者本地运行,CI 不持有 Token;快照去除会员、订单、券码等个人数据

## 6. 部署

- 主站 GitHub Pages(`<user>.github.io/mcd-lite-calc`),镜像 Netlify(`*.netlify.app`)。2026-10-14 武汉联通实测两者 200 可达;Vercel 超时,Cloudflare Pages 不稳定
- 页面不引用任何外部 CDN、字体、统计脚本

## 7. 测试

- `mcdcalc`:匹配四级顺序、双层防串号、去配料区间累加、override 优先、套餐子项相加、unmatched 处理、每单一券、麦金卡净额、分整数运算、推荐三方案约束成立
- 数据自洽:`modification-calories.json` 与 `modification-options.raw.json` code 集合一致;每条有 kcal/range/method/confidence
- `build_web.py`:产物 schema 校验、972 档位齐全、体积上限
- CI:pytest 失败则不部署

## 8. 排期

| 天 | 内容 |
|---|---|
| D1–3 (10/14–16) | core/data 整理、mcdcalc 三模块 + 测试 |
| D4–6 (10/17–19) | snapshot.py、build_web.py、演示页 |
| D7–8 (10/20–21) | Skill + MCP 联调 |
| D9–10 (10/22–23) | README、MCP_INTEGRATION、宣发图、部署 Pages/Netlify、报名 Issue |
| D11 (10/24) | 缓冲 |

## 9. 已知局限

- 酱料热量 9 项为低置信估算,展示时标"估"与区间
- 早餐菜单特制未采集(需早餐时段重跑 collect)
- 演示页数据为单店快照,与用户所在门店菜单/券可能不同
- 培根、麦香鱼芝士份量按美国惯例推断,未在国内核实
