# 掘金文章草稿

- 标题：麦当劳官方 MCP 开发大赛作品：配料级热量、区间传播和 2ⁿ 预计算
- 备选 A：参加麦当劳程序员节大赛，我写了个让 AI 算热量再下单的 Skill
- 备选 B：巨无霸去掉酱少 136 卡：一个麦当劳 MCP Skill 的技术实现
- 标签：MCP、AI、Claude、Python、前端
- 分类：人工智能
- 封面：docs/promo/hero.png
- 发布方式：掘金编辑器支持 Markdown，图片拖进去自动上传，`![]()` 处按文件名替换

---

> **求 Star**：这是麦当劳程序员节创意开发大赛的参赛作品。比赛按 GitHub Star 数排名，**10 月 25 日 23:59 截止**。觉得这篇有收获，麻烦去仓库点个 Star：https://github.com/FarSightLi/mcd-lean-maker

## 比赛是什么

麦当劳中国 2025 年 12 月上线了官方 MCP Server（`https://mcp.mcd.cn`），AI 可以通过它查门店、查菜单、核价、下单。今年程序员节，麦当劳在 GitHub 官方账号下发起了创意开发大赛，要求基于这套 MCP 开发 Skill：

- 比赛仓库：https://github.com/M-China/mcd-developer-innovation-challenge
- 报名方式：作品开源到 GitHub，在比赛仓库提 Issue 报名
- 排名规则：按项目获得的公开 Star 数排名，截止到 10 月 26 日 00:00

我的作品叫**麦麦减脂助手**。它要解决的问题很具体：巨无霸去掉酱，能少多少卡？

答案是 136 卡。整份 513 kcal，去掉巨无霸酱和吉士后约 377 kcal（351–399）。

![巨无霸去掉酱和吉士前后对比](https://cdn.jsdelivr.net/gh/FarSightLi/mcd-lean-maker@feature-mcd-lite-calc-20261014/docs/promo/bigmac-compare.png)

- 作品仓库：https://github.com/FarSightLi/mcd-lean-maker
- 在线体验（不用 Token，打开就能用）：https://farsightli.github.io/mcd-lean-maker/

下面讲实现。

## 架构

```
麦当劳 MCP ──┬─ Skill（AI 对话）：选店 → 搭配 → calc.py 计算 → calculate-price 核价 → create-order
             └─ tools/snapshot.py → build_web.py 预计算 → 静态网页 / serve.py 实时网页
```

同一个计算内核 `mcdcalc` 有两个入口：

- **Skill**：AI 在对话中调用 MCP，热量交给 `calc.py` 计算
- **网页**：构建时调用 MCP 拉一份快照并预计算，运行时不再访问 MCP

Skill 用到了 11 个 MCP 工具，主链路是这样：

```
query-nearby-stores 选店
→ query-meals / query-meal-detail 匹配商品和特制项（modification code）
→ calc.py 算热量：513 → 377 kcal（351–399）
→ calculate-price 实时核价（含券、麦金卡随单购）
→ 展示确认卡 → 用户确认 → create-order → query-order
```

`SKILL.md` 里给 AI 定了三条硬约束：

- 热量由脚本计算，大模型不心算。数字一旦出错就是误导，脚本的结果可以复现，也能写测试
- 价格只认 `calculate-price` 的返回值，不用菜单价自己加减
- 用户没说"确认"之前不调用 `create-order`。换店、换商品、改特制之后都要重新核价，重新出确认卡

## 难点一：MCP 只给整份营养，配料热量要自己推导

`list-nutrition-foods` 只返回整份商品的营养。`query-meal-detail` 能告诉你"巨无霸可以去巨无霸酱"，但不告诉你这份酱有多少卡。

我把 23 个特制项的热量差逐项推导出来，写进 `data/modification-calories.json`，每项都附带推导过程。推导按三种方法依次取值：

**A 成对相减。**在营养表里找只差一种配料的两款商品：

```
吉士 = 吉士汉堡包 294 − 汉堡包 248 = 46 kcal
```

蛋白、脂肪、钠、钙按同样方法相减，这一档最可靠。

**B 海外数据校准。**先对比中美同款的基础配方（汉堡包 248 vs 250，吉士汉堡 294 vs 300）。配方接近，再采用美国官网或 USDA 的单项数据。

**C 同类估算。**酱料基本没有直接数据，按同类食材的通用值估算，区间放宽。

实际分布是 A 法 1 项、B 法 3 项、C 法 19 项。大部分数字是估出来的，所以每个结果都带区间和置信度，页面上会如实标出来。

![数据口径说明](https://cdn.jsdelivr.net/gh/FarSightLi/mcd-lean-maker@feature-mcd-lite-calc-20261014/docs/promo/truth.png)

## 难点二：区间传播

每个配料存成 `[low, high]`。去掉配料时往保守方向算，保证真实值一定落在区间里：

```
新下限 = 原下限 − 配料上限
新上限 = 原上限 − 配料下限
```

区间在两种情况下会累积：一次去掉多项配料，或者套餐的多个子项相加。置信度取所有组成部分里最低的那一档。

这部分有专门的测试覆盖（`test_nutrition_remove.py`、`test_nutrition_sum.py`），整个仓库目前 80 个用例。

## 难点三：纯静态页怎么做到秒开

在线体验页托管在 GitHub Pages 上，没有后端，也不持有 Token。做法是构建时把所有状态算完，运行时只查表。

**去配料是 2ⁿ 个状态。**一个商品有 n 个可去配料，就只有 2ⁿ 种组合。用位掩码当键，第 i 位为 1 表示去掉第 i 项。前端拨一下开关就是翻转一个 bit，再查一次表：

```
https://farsightli.github.io/mcd-lean-maker/?item=1100&mask=3
# 1100 = 巨无霸
# mask=3 = 0b11 → 去掉第 0 项（巨无霸酱）和第 1 项（吉士）
```

分享链接和分享卡二维码编码的都是这个 `mask`，打开就能还原同一份配料。

**推荐方案是 9301 个格子。**

1. 商品分成主食、小食、饮品、甜品、套餐五类
2. 枚举不超过 3 件的组合，去掉不像一顿饭的组合（单品、纯甜品、纯饮品）
3. 预算 71 档 × 热量上限 131 档，共 9301 格，每格挑出最低卡、高蛋白、最省钱三套
4. 去重后真正被选中的组合只有 132 个，格子里只存组合下标，`recommend.json` 因此很小

拖滑块时同样只是查表。

![预算 × 热量推荐方案](https://cdn.jsdelivr.net/gh/FarSightLi/mcd-lean-maker@feature-mcd-lite-calc-20261014/docs/promo/plan.png)

## 难点四：跨域图片画进 canvas 会报错

分享卡要画商品图。图片在 `menu-img.mcd.cn` 上，响应头没有 `Access-Control-Allow-Origin`。

`<img>` 显示没问题，但图片画进 canvas 后画布会被标记为 tainted，`toDataURL` 直接抛 `SecurityError`。

我的处理是构建时把图片下载到同源目录，顺带转成 WebP（7.6 MB → 1.3 MB）。图片加载失败时退回纯文字卡片。二维码用仓库内置的 qrcode-generator 在本地 canvas 上绘制，不依赖外部服务。

![分享卡](https://cdn.jsdelivr.net/gh/FarSightLi/mcd-lean-maker@feature-mcd-lite-calc-20261014/docs/share-card.png)

## 难点五：麦金卡净价要实测，不能算

开卡后的实付 = 可随单购商品的会员价 + 其余商品现价 + 一次月卡费。

哪些商品能随单购、会员价是多少，只能带 `withOrder` 参数调 `calculate-price` 拿到真实结果。比如麦辣鸡腿堡四件套原价 ¥57，开卡后 ¥28 加卡费 ¥19 共 ¥47，`offers.py` 会给出"开卡省 ¥10"。

## 安全上的几个处理

- Token 只从环境变量读取，仓库里只有 `mcp-config.example.json` 占位
- 本地服务只监听 `127.0.0.1`，Token 不写文件，也不传给前端
- 快照在 `snapshot.py` 里脱敏，去掉会员、订单、券码，只留商品、营养、价格这些公开信息

## 三步用起来

1. 去 https://open.mcd.cn/mcp 申请 Token，接入 Claude Code、Cursor、Trae、Cherry Studio 或 WorkBuddy
2. 把 `skill/mcd-lean-maker` 复制到技能目录（`calc.py` 只依赖 Python 标准库）
3. 对 AI 说："麦当劳午饭 600 卡以内，30 块钱，怎么点"

---

## 求个 Star

比赛按 GitHub Star 排名，**10 月 25 日 23:59 截止**。如果这篇里的位掩码预计算、区间传播或 canvas 跨域处理对你有用，麻烦点个 Star 支持一下：

👉 **https://github.com/FarSightLi/mcd-lean-maker**

C 档那 19 项估算最缺可靠的数据来源，欢迎提 issue 纠正。想自己参赛的话，报名入口在比赛仓库：https://github.com/M-China/mcd-developer-innovation-challenge

*本项目是参赛作品，由个人独立开发，不是麦当劳官方产品。热量数据仅供参考。*
