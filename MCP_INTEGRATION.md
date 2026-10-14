# MCP 集成说明

## 使用的 MCP Server

- 地址:`https://mcp.mcd.cn`
- 协议:`streamablehttp`
- 鉴权:`Authorization: Bearer ${MCD_MCP_TOKEN}`,Token 来自平台 MCP 连接器或本地环境变量,仓库内只保留 `mcp-config.example.json` 占位配置,不包含任何真实 Token

## 工具清单

| 工具 | 调用阶段 | 用途 | 业务价值 |
|---|---|---|---|
| `query-nearby-stores` | 选店 | 查询用户附近/收藏门店 | 确定计算与下单的门店口径 |
| `query-meals` | 推荐 | 查询门店菜单(含新品标记) | 作为去配料计算与推荐方案的候选商品来源 |
| `query-meal-detail` | 选品去配料 | 查询商品组成与特制(modification)选项 | 把"去酱""去吉士"等用户说法映射为 modification code,供本地重算热量 |
| `query-store-coupons` | 核价 | 查询门店维度可用优惠券 | 核价时纳入券优惠,得到更接近真实的到手价 |
| `available-coupons` | 推荐(可选) | 查询用户当前可领取的优惠券 | 发现用户尚未领取但可用的优惠,征得同意后再领取 |
| `auto-bind-coupons` | 推荐(可选) | 一键领取当前可领的优惠券 | 领券前征得用户同意后执行,避免代用户做决定 |
| `calculate-price` | 核价 | 计算商品价格(含优惠、随单购、麦金卡) | 得到含券/麦金卡的真实净价,`calc.py` 据此对比开卡与否 |
| `create-order` | 下单 | 创建订单 | 用户明确说"确认下单"后才调用,引导到 App 完成支付 |
| `query-order` | 下单后 | 查询订单状态 | 用户回复支付完成/失败后,核实最新订单状态 |
| `cancel-order` | 下单后(可选) | 取消订单 | 用户主动要求取消时使用 |
| `list-nutrition-foods` | 数据准备 | 查询常见餐品营养成分 | 维护者本地拉取营养快照,是配料级热量计算的基础数据来源 |

## 调用流程

```
选店 (query-nearby-stores)
  → 菜单/新品 (query-meals)
  → 商品详情/特制选项 (query-meal-detail)
  → 本地计算 (calc.py: 去配料热量、方案推荐)
  → 核价 (calculate-price, 可选 query-store-coupons / available-coupons / auto-bind-coupons)
  → 确认 (向用户展示门店、商品与特制、热量区间、券、实付、取餐方式)
  → 下单 (create-order → query-order,用户明确确认后才执行)
```

每一步改动(换店、换商品、改特制)后都重新核价并重新生成确认卡;一次确认只对应一单。

## 演示页数据流

演示页不持有 Token,也不在运行时调用 MCP:

```
维护者本地 (MCD_MCP_TOKEN) → tools/snapshot.py 拉取并脱敏 → web/snapshot/
  → tools/build_web.py 调用 mcdcalc 预计算 → web/data/*.json
  → GitHub Pages / Netlify 静态托管
```

`snapshot.py` 只在维护者本地运行,CI 构建阶段不持有也不需要 Token;快照已去除会员、订单、券码等个人数据,只保留商品、营养、价格等公开信息。

## 业务价值

- **配料级热量**:把"去酱""去吉士""去培根"等用户常见诉求,转成每一项的具体 kcal 增减区间与置信度,而不是只传一个布尔参数
- **麦金卡真实净价**:通过 `calculate-price` 实测随单购+月卡费的真实组合价,明确告知"开卡划算"还是"开卡更贵",而不是停留在营销话术层面
