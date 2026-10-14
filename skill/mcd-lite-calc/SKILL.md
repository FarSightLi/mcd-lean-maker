---
name: mcd-lite-calc
description: 麦当劳去配料热量与优惠计算(非官方)。当用户想知道麦当劳某个汉堡/套餐去掉酱、芝士、培根等配料后的热量,想在预算和热量限制下点麦当劳,想比较开麦金卡是否划算,或想找麦当劳今日新品并下单时使用。基于麦当劳中国 MCP 实时菜单、营养表与核价。
---

# 麦麦减卡计算器

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
- 只有用户明确说"确认下单"才调 `create-order`;"下单""试试""可以吧"等都不算确认,需再问一次
- 确认后用户改任何内容 → 重新 `calculate-price`、重新出确认卡、重新确认
- 一次确认只创建一单;支付由用户在 App 完成
- 领券、开卡都要先征得同意

详见 `references/mcp-tools.md`、`references/offers-rules.md`。
