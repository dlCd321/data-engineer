# Q6.1 - AI 协作反向分析（选做，10 分）

## 选定的题目：Q1 数据质量探索与清洗策略

我选择 Q1，是因为这道题看起来只是做 EDA，但真正难点不是写 `describe()`，而是把异常值解释成业务语义：哪些是退货，哪些是 bad debt，哪些是邮费/折扣/平台费用，哪些是商品损坏或库存损耗。如果只依赖 AI 的第一版建议，很容易得到一个“看起来完整、但口径混乱”的答案。

## 1. 你的第一个 Prompt

```
[$data-analysis] 我q1里的notebook还可以探索什么方面
```

**为什么这样写**：

当时我已经做了基础的数据加载、缺失值、重复值和 `describe()`，但不知道怎么把异常现象整理成题目要求的“非显而易见的数据质量问题”。所以我没有直接让 AI 代写答案，而是让它先帮我找还可以继续探索的方向。这样可以把 AI 当成 checklist，再由我自己回到 notebook 里验证每一条是否真的成立。

这个 prompt 的不足是太宽泛，没有告诉 AI 我已经观察到哪些异常，也没有要求它区分“销售分析口径”“库存分析口径”“财务口径”。所以 AI 第一版回答有方向价值，但还不能直接作为最终答案。

---

## 2. AI 的回答

```
我看了 q1_code.ipynb 和 Q1 题目要求。现在 notebook 还只是基础 EDA，可以往这些方向补，优先级从高到低：

1. 非产品 StockCode 分类
不只是看 value_counts()，要把特殊码分组解释：
- POST / DOT / C2：邮费、dotcom postage、carriage
- D：折扣
- M：manual adjustment
- BANK CHARGES / AMAZONFEE / CRUK：费用/佣金
- gift_0001_*：礼品券
- 这些特殊码共 6,094 行，占约 0.57%，金额占比约 -0.49%

2. 极端 Quantity 不要直接当异常删
最大 80995 和最小 -80995 是同一商品、同一客户、间隔 12 分钟的销售与取消：
- 581483 / 23843 / 80995
- C581484 / 23843 / -80995
这可以作为“看起来异常，但其实有业务解释”的强案例。

3. 负数和 0 价格分开看
- Price < 0 只有 5 行，都是 bad debt adjustment
- Price = 0 有 6,202 行，很多是 lost、damaged、short、check、缺失描述
- Quantity < 0 不全是取消单：有 3,457 行是数字 Invoice + 0 价格，多半是库存损耗/调整

4. Customer ID 缺失群体画像
- 缺失 Customer ID：243,007 行，占 22.77%
- 但金额只占约 13.68%
- 98.77% 来自 UK
- 平均行金额 10.86，有 Customer ID 的是 20.20
- 高频商品里有 DOTCOM POSTAGE，可以推测偏匿名线上/系统渠道/未绑定客户订单

5. 重复行是否真重复
- 精确重复行有 34,335 行
- 但数据没有 invoice line id，同一订单同一商品可能真实出现多行
- 所以不能无脑 drop duplicate，要看下游用途决定

6. Description 和 StockCode 的错配
- 有些 StockCode 对应多个描述
- 说明 Description 混入了库存/人工备注，不总是商品名

7. 缺失 Description 的业务含义
- 缺失 Description 有 4,382 行，而且：
- Price 全部是 0
- Customer ID 全部缺失
- 约 61% 是负 Quantity
这比单纯说“Description 有缺失”强很多。

8. 时间范围和月度可比性
数据到 2011-12-09，所以 2011 年 12 月不是完整月份。后续如果做月度趋势，不能直接把 2011-12 和其他完整月份比较。

建议 notebook 最后加一个“小结 cell”，把这些探索收敛成 Q1.1 的 5 个以上数据质量问题，并明确哪些应该删除、哪些应该保留、哪些要按下游用途分开处理。当前最缺的是“业务解读”和“清洗策略口径”，不是更多 describe()。
```

---

## 3. 你迭代了几轮 Prompt？

我围绕 Q1 迭代了 3 轮：

1. 第一轮让 AI 给探索方向，得到特殊 StockCode、极端 Quantity、Price/Quantity 异常、Customer ID 缺失、重复行、Description 异常等候选问题。
2. 第二轮我在 notebook 中逐项验证 AI 的说法，比如查 `C` 前缀 invoice、`A` 前缀 bad debt、`Price < 0`、`Price = 0`、`Quantity < 0` 的交叉情况。
3. 第三轮发现 `Price = 0` 且 `Quantity < 0` 的记录很多不是退货，而是商品损坏/库存损耗，于是要求 AI 修改 notebook 的分类口径，把这类记录标记为 `IsDamageOrInventoryLoss`。

---

## 4. AI 的最终答案有什么错误或不足？

> 你是怎么发现并修正的？

AI 的主要不足不是代码语法，而是业务口径不够精确。

第一，AI 一开始把 `Price = 0` 且 `Quantity < 0` 概括成“库存损耗/调整”。这个方向大体对，但还不够具体。我在 notebook 里把这些行筛出来后，看到大量 `Description` 是 `damaged`、`damages`、`smashed`、`thrown away`、`unsaleable, destroyed`、`wet damaged`，所以我判断它们更应该明确写成“商品损坏/库存损耗”，而不是普通退货，也不是销售收入异常。

第二，AI 给出的建议如果直接使用，容易把所有 `Quantity < 0` 都当作一类问题。但实际数据里至少有三类负数量：`C` 开头 invoice 是取消/退货；极端的 `-80995` 是一笔大额订单快速取消；数字 invoice 且 `Price = 0` 的负数量更像损坏、盘点或系统调整。这三类在清洗时不能用同一个规则删除。

第三，AI 的回答没有强制区分下游分析口径。我最后把 Q1 小结改成分层处理：gross product sales 排除零价损耗；net product sales 纳入退货抵减；库存/运营质量口径保留损坏和盘点记录；财务总额口径保留所有金额行但分组展示。

我的修正方法是回到原始数据验证，而不是直接相信 AI：

```python
work.loc[work["IsDamageOrInventoryLoss"], "Description"] \
    .fillna("<missing>") \
    .str.upper() \
    .value_counts() \
    .head(20)
```

验证结果显示这类记录共有 3,457 行，高频描述包括 `<MISSING>`、`CHECK`、`DAMAGED`、`DAMAGES`、`SMASHED`、`THROWN AWAY`、`UNSALEABLE, DESTROYED.` 等。这说明它们在销售分析里应该排除，但在库存质量分析里应该保留。

---

## 5. 如果让你再做一次同样的题，你的第一个 prompt 会怎么写？

我会把第一个 prompt 写得更具体，直接要求 AI 按“业务语义”和“清洗口径”输出，而不是只给探索方向：

```
我在做 Online Retail II 的 Q1 数据质量分析。当前字段有 Invoice、StockCode、Description、Quantity、InvoiceDate、Price、Customer ID、Country。

我已经发现：
1. Invoice 有 C/A 前缀；
2. Quantity 有极端正负值；
3. Price 有负数和 0；
4. Customer ID 和 Description 有缺失；
5. 有重复行。

请不要直接替我写最终答案。请给我一个验证清单：
- 每个异常应该用什么 pandas 查询验证；
- 它可能代表什么业务语义；
- 它应该进入哪个分析口径：gross sales、net sales、customer/RFM、inventory quality、financial total；
- 哪些异常不能直接删除；
- 哪些地方最容易被 AI 误判。

特别注意区分：
- C 开头 invoice 的取消/退货；
- A 开头 invoice 的 bad debt；
- Price=0 且 Quantity<0 的商品损坏或库存损耗；
- 非产品 StockCode，如 POST、DOT、D、M、BANK CHARGES、AMAZONFEE。
```

这样写会比我原来的 prompt 更好，因为它提前约束了 AI 的输出结构，也把最容易混淆的几类异常放在一起比较。AI 适合帮我生成验证路径，但最终业务解释必须由我用数据结果确认。
