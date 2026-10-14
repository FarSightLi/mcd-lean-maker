# MCP 工具清单

本 Skill 在点餐流程中调用以下 10 个麦当劳 MCP 工具。与仓库根目录 `MCP_INTEGRATION.md` 的工具表核对一致:该表另有 `list-nutrition-foods`,是维护者本地拉取营养快照的数据准备工具,不在本 Skill 的实时调用链路里,因此本表不重复收录。

| 工具 | 用途 | 必填参数 | 易错点 |
|---|---|---|---|
| `query-nearby-stores` | 查询用户附近/收藏门店 | `searchType`(2=按位置)、`beType`(1=到店自取);`searchType=2` 时还需 `city`、`keyword` | `beType=1`(到店自取)返回的门店**不带** `beCode`,后续调用也不传 `beCode`;只有 `beType=5`(得来速)才有 `beCode` 且后续必传 |
| `query-meals` | 查询门店菜单(含新品标记) | `storeCode`、`orderType`、`beType` | 到店自取(`beType=1`)场景不传 `beCode`;新品靠 `tags` 字段里含"上新"判断,不要只看商品名 |
| `query-meal-detail` | 查询商品组成与特制(modification)选项 | `storeCode`、`orderType`、`beType`、`code` | `modification` 组内若存在 `unselectedKey`,则组内**所有**选项都要传:用户选中的传 `selectedKey`,未选中的传 `unselectedKey`,不能只传选中项 |
| `query-store-coupons` | 查询门店维度可用优惠券 | `storeCode`、`orderType`、`beType` | 返回的券只对当前门店+订单类型有效,不能跨门店复用;到店自取不传 `beCode` |
| `available-coupons` | 查询用户当前可领取的优惠券 | 无 | 只是展示可领列表,不代表已领到,领取前要先征得用户同意 |
| `auto-bind-coupons` | 一键领取当前可领的优惠券 | 无 | 必须先征得用户同意才调用,不能自动代领 |
| `calculate-price` | 计算商品价格(含优惠、随单购、麦金卡) | `storeCode`、`orderType`、`beType`、`items` | 价格字段单位为"分"(fen),不是元;`takeWayCode` 要从返回的 `data.takeWayList[].code` 里取(如 `eat-in`、`take-in-store`),不能自己猜;`withOrder` 传会员随单购信息(`membershipCode`、`membershipSpecId`)时,返回的 `productList` 会多一行麦金卡月卡(如"麦金卡月卡（30天）1900"分),卡费只在一单里算一次 |
| `create-order` | 创建订单 | `storeCode`、`orderType`、`beType`、`items`;到店/得来速场景还需 `takeWayCode` | 只有用户明确说"确认下单"才能调用;一次确认只创建一单,一单只能用一张券 |
| `query-order` | 查询订单状态 | `orderId` | 用户回复"支付完成/支付失败"后才查,不要主动轮询 |
| `cancel-order` | 取消订单 | `orderId`、`cancelReasonCode` | 用户主动要求取消时才调用,不要代用户决定取消 |
