# 麦麦减卡计算器

去掉酱、芝士、培根各少多少卡,怎么点最省钱,一页算清。

在线体验:[Pages 主站](https://<user>.github.io/mcd-lite-calc/) · [Netlify 镜像](https://<site>.netlify.app/)

![首屏截图](docs/preview.png)

## 亮点

- **配料级热量**:23 个特制项(去酱、去芝士、去培根等)逐项标出 kcal 增减区间与置信度,不是笼统的"少吃点"
- **预算 × 热量三套方案**:输入预算和热量上限,给出最省钱、最低卡、性价比三套搭配
- **麦金卡真实净价**:实测随单购+月卡费的真实组合价,明确"开卡划算"还是"开卡更贵"
- **今日新品**:快照中标记"上新"的商品,营养数据标注"估算"
- **分享卡**:一键生成可下载/保存的计算结果图片

## 和别人有什么不一样

参赛榜单上能"去酱"的项目,大多只是把这个选项当参数传给下单接口,并不计算具体少了多少热量;本项目把每一个特制项的热量变化都量化出来。

## 给普通用户

打开上面的在线体验链接即可使用,无需安装、无需登录、不会产生真实下单。

## 给开发者

### 安装 Skill

把 `skill/mcd-lite-calc` 整个目录复制到 Claude 的技能目录(`~/.claude/skills/`)或 WorkBuddy 技能目录即可使用。

按 `mcp-config.example.json` 配置 MCP 连接:

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

Token 通过环境变量 `MCD_MCP_TOKEN` 提供,不要把真实 Token 写进配置文件或提交到仓库。

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
| 快照价格 | 演示页价格来自某日某门店快照,与你所在门店实际售价可能不同 |

示例:巨无霸去掉"巨无霸酱"和"吉士"后,热量由 513 kcal 降至约 377 kcal(区间 351–399);麦辣鸡腿堡四件套原价 ¥57,随单购后 ¥28 + 月卡 ¥19 = ¥47(2026-10-14 实测)。

## 开发

```bash
.venv/bin/python -m pytest -q                                           # 运行测试(在仓库根目录执行)
PYTHONPATH=skill/mcd-lite-calc/scripts .venv/bin/python tools/snapshot.py        # 本地拉取并脱敏快照(需 MCD_MCP_TOKEN)
PYTHONPATH=skill/mcd-lite-calc/scripts:tools .venv/bin/python tools/build_web.py # 预计算并生成 web/data
```

## 声明

本项目为非官方作品,基于麦当劳中国 MCP 开发,不代表麦当劳官方立场,也不构成官方优惠或下单渠道。参赛声明见 [CONTEST_DECLARATION.md](CONTEST_DECLARATION.md)。
