# 麦麦减脂助手

去掉酱、芝士、培根各少多少卡,怎么点最省钱,一页算清。

**[直接打开网页(无需安装)](https://farsightli.github.io/mcd-lean-maker/)**

<img src="docs/preview.png" alt="首屏截图" width="320"> <img src="docs/share-card.png" alt="分享卡样图" width="320">

## 亮点

- **配料级热量**:23 个特制项(芥末酱、番茄片各出现在两款商品里,去重后 21 种配料)逐项标出 kcal 增减区间与置信度
- **预算 × 热量三套方案**:输入预算和热量上限,按最低卡、高蛋白、最省钱给出三套搭配;方案里的商品可直接点开查看去配料明细
- **麦金卡真实净价**:实测随单购+月卡费的真实组合价,明确"开卡划算"还是"开卡更贵"
- **快照新品**:快照中标记"上新"的商品,营养数据标注"估算"
- **分享卡**:生成带二维码的计算结果图片,扫码打开同款配料
- **深链**:`?item=<商品code>&mask=<去配料位掩码>`,套餐用 `&c=<轮次>:<子项code>:<掩码>,...`

## 做法

每个特制项的热量变化单独量化:优先用营养表同款成对相减,其次用海外官方数据校准,最后才用同类食材估算,并标注置信度与区间。下单仍交给 Skill 调用麦当劳 MCP 完成。

## 给普通用户

打开上面的网页链接即可使用,无需安装、无需登录、不会产生真实下单。热量与营养为参考估算,不构成营养或医疗建议。

## 给开发者

### 安装 Skill

需要 Python ≥ 3.10(`scripts/calc.py` 仅用标准库)。

需在本地 AI 工具(支持 MCP 与 Skill 的 AI 编程助手/客户端)中配置麦当劳 MCP 并安装本 Skill。把 `skill/mcd-lean-maker` 整个目录复制到所用工具的技能目录即可,例如 Claude Code 的 `~/.claude/skills/` 或 WorkBuddy 技能目录:

```bash
git clone https://github.com/FarSightLi/mcd-lean-maker.git
cp -r mcd-lean-maker/skill/mcd-lean-maker ~/.claude/skills/
```

添加麦当劳 MCP(HTTP 传输),以 Claude Code 为例:

```bash
claude mcp add --transport http mcd-mcp https://mcp.mcd.cn \
  --header "Authorization: Bearer $MCD_MCP_TOKEN"
```

添加后在 Claude Code 里运行 `/mcp` 确认状态为 connected。其他客户端按 `mcp-config.example.json` 的 JSON 配置:

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

Token 从麦当劳 MCP 平台连接器获取,通过环境变量 `MCD_MCP_TOKEN` 提供,不要把真实 Token 写进配置文件或提交到仓库。

> **TODO:获取 Token 的具体步骤:待补充**

配置好后,可以直接对 AI 说(网页方案卡和商品弹层里的"交给 AI 下单"按钮会复制同类话术):

```
用麦麦减脂助手 Skill,帮我在附近麦当劳到店自取:巨无霸(去巨无霸酱、吉士)+ 美式,预算 30 元、热量 600 kcal 以内,先给我确认卡再下单
```

### 使用示例对话

```
用户:帮我在附近门店点一个巨无霸,去掉酱和吉士
助手:(query-nearby-stores 选店 → query-meals/query-meal-detail 匹配商品与特制
      → 本地计算:巨无霸 513 → 377 kcal,区间 351–399
      → calculate-price 核价 → 展示确认卡)
用户:确认下单
助手:(create-order → 引导支付 → query-order 查状态)
```

## 数据真实性对照表

| 类型 | 说明 |
|---|---|
| 官方 | 来自 `list-nutrition-foods` 等 MCP 接口的营养与价格数据 |
| 估算 A | 有同类商品数据外推,置信度较高 |
| 估算 B | 参考同类项或常识推断,置信度中等 |
| 估算 C | 低置信估算(如 9 项酱料热量),展示时标"估"与区间 |
| 去配料后营养 | 去掉的配料有营养明细时按估算扣除,没有明细时沿用原值,标"约";NRV 依据 GB 28050,以成人每日 8400 kJ 为参考 |
| 快照价格 | 演示页价格来自某日某门店快照,与你所在门店实际售价可能不同 |

示例:巨无霸去掉"巨无霸酱"和"吉士"后,热量由 513 kcal 降至约 377 kcal(区间 351–399);麦辣鸡腿堡四件套原价 ¥57,随单购后 ¥28 + 月卡 ¥19 = ¥47(2026-10-14 实测)。

## 开发

```bash
.venv/bin/python -m pytest -q                                           # 运行测试(在仓库根目录执行)
PYTHONPATH=skill/mcd-lean-maker/scripts .venv/bin/python tools/snapshot.py        # 本地拉取并脱敏快照(需 MCD_MCP_TOKEN)
PYTHONPATH=skill/mcd-lean-maker/scripts:tools .venv/bin/python tools/build_web.py # 预计算并生成 web/data(需 pillow==12.3.0 转 WebP,缺失时保留原图)
```

### 本地实时模式

默认打开的是仓库里固定的快照演示页。如果想用自己门店的实时数据,可以在本机起一个只服务给自己的本地后端:

```bash
export MCD_MCP_TOKEN=你的token
PYTHONPATH=skill/mcd-lean-maker/scripts:tools python3 tools/serve.py
```

然后打开 `http://127.0.0.1:8000/`,页面顶部会出现门店搜索栏:输入城市和门店关键词搜索,选中门店后拉取该店实时菜单(约 30–60 秒),页面会自动用实时数据重新渲染所有模块。

说明:

- `tools/serve.py` 只监听 `127.0.0.1`,仅本机可访问,不会被局域网或公网其他设备连接到
- Token 只从环境变量 `MCD_MCP_TOKEN` 读取,不写入任何文件、不回传给前端
- 网页本身不下单,所有下单操作都在 Skill 内完成(见上文「安装 Skill」)

## 声明

本项目为非官方作品,基于麦当劳中国 MCP 开发,不代表麦当劳官方立场,也不构成官方优惠或下单渠道。参赛声明见 [CONTEST_DECLARATION.md](CONTEST_DECLARATION.md)。
