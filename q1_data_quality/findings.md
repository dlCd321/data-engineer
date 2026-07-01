# Q1.2 数据真实结构发现

以下结论由 `q1_code.py` 复现。核心派生字段包括 `InvoicePrefix`、`LineAmount = Quantity * Price`、`IsCancellation`、`IsBadDebtAdjustment`、`IsDamageOrInventoryLoss`、`IsCustomerMissing` 和 `StockCodeCategory`。

## 问题 1：InvoiceNo 不只是数字

支持代码：

```python
work.groupby("InvoicePrefix").agg(
    rows=("Invoice", "size"),
    invoices=("InvoiceStr", "nunique"),
    quantity_sum=("Quantity", "sum"),
    amount_sum=("LineAmount", "sum"),
    negative_quantity_rows=("Quantity", lambda s: int((s < 0).sum())),
    negative_price_rows=("Price", lambda s: int((s < 0).sum())),
)
```

结果：

| InvoicePrefix | 行数 | invoice 数 | Quantity 合计 | 金额合计 | 负数量行 | 负价格行 |
|---|---:|---:|---:|---:|---:|---:|
| numeric | 1,047,871 | 45,330 | 11,099,478 | 20,961,532.51 | 3,457 | 0 |
| C | 19,494 | 8,292 | -490,992 | -1,526,667.86 | 19,493 | 0 |
| A | 6 | 6 | 6 | -147,614.08 | 0 | 5 |

解读：

- `C` 是 cancellation/return。几乎所有 `C` 行都是负数量，应作为退货或取消抵减，而不是普通销售。
- `A` 是 bad debt adjustment。它只有 6 行，其中 5 行价格为负，Description 都是 `Adjust bad debt`，业务上不是商品销售。
- 做销售总额时建议同时区分三种口径：
  - **Gross product sales = 20,108,995.40**：只看正向商品销售，作为主销售指标。
  - **Net product sales = 19,382,476.01**：纳入 `C` 取消/退货抵减，用于看净商品销售。
  - **Financial total = 19,287,250.57**：保留邮费、折扣、费用、坏账等全部金额，只适合财务对账，不适合作为商品销售额。

## 问题 2：StockCode 也不只是产品

支持代码：

```python
work["StockCodeCategory"] = work["StockCodeStr"].map(classify_stock_code)
work.groupby("StockCodeCategory").agg(
    rows=("Invoice", "size"),
    distinct_codes=("StockCodeStr", "nunique"),
    amount_sum=("LineAmount", "sum"),
)
```

宽分类结果：

| 分类 | 行数 | distinct codes | 金额合计 | 行数占比 | 金额占比 |
|---|---:|---:|---:|---:|---:|
| product_like | 1,061,278 | 5,242 | 19,382,476.01 | 99.429% | 100.494% |
| postage_carriage_dotcom | 3,850 | 3 | 448,374.47 | 0.361% | 2.325% |
| manual_adjustment | 1,496 | 4 | -75,214.98 | 0.140% | -0.390% |
| sample_test_internal | 298 | 38 | -4,728.03 | 0.028% | -0.025% |
| discount | 177 | 1 | -13,484.54 | 0.017% | -0.070% |
| fees_commission_bad_debt | 167 | 4 | -451,873.72 | 0.016% | -2.343% |
| gift_voucher | 101 | 10 | 1,686.61 | 0.009% | 0.009% |
| other_non_product_or_unknown | 4 | 2 | 14.75 | 0.000% | 0.000% |

非产品代码列表：

| 分类 | 代码 |
|---|---|
| postage_carriage_dotcom | `C2`, `DOT`, `POST` |
| discount | `D` |
| manual_adjustment | `ADJUST`, `ADJUST2`, `M`, `m` |
| fees_commission_bad_debt | `AMAZONFEE`, `B`, `BANK CHARGES`, `CRUK` |
| gift_voucher | `GIFT`, `gift_0001_10`, `gift_0001_20`, `gift_0001_30`, `gift_0001_40`, `gift_0001_50`, `gift_0001_60`, `gift_0001_70`, `gift_0001_80`, `gift_0001_90` |
| sample_test_internal | `DCGS0003`, `DCGS0004`, `DCGS0006`, `DCGS0016`, `DCGS0027`, `DCGS0036`, `DCGS0037`, `DCGS0039`, `DCGS0041`, `DCGS0044`, `DCGS0053`, `DCGS0055`, `DCGS0056`, `DCGS0057`, `DCGS0058`, `DCGS0059`, `DCGS0060`, `DCGS0062`, `DCGS0066N`, `DCGS0066P`, `DCGS0067`, `DCGS0068`, `DCGS0069`, `DCGS0070`, `DCGS0071`, `DCGS0072`, `DCGS0073`, `DCGS0074`, `DCGS0075`, `DCGS0076`, `DCGSLBOY`, `DCGSLGIRL`, `DCGSSBOY`, `DCGSSGIRL`, `PADS`, `S`, `TEST001`, `TEST002` |
| other_non_product_or_unknown | `C3`, `SP1002` |

解读：这些代码行数占比不高，但金额影响明显，尤其是 postage/dotcom 和 fees/bad debt。商品销量、热销 SKU、商品推荐模型应排除非产品代码；财务分析可以保留，但必须单独分组。

## 问题 3：可疑的极端值

支持代码：

```python
work.loc[
    work["Quantity"].isin([work["Quantity"].max(), work["Quantity"].min()]),
    ["Invoice", "StockCode", "Description", "Quantity", "InvoiceDate", "Price", "Customer ID", "LineAmount"],
]

work.loc[work["Price"] < 0]
```

Quantity 极值：

| Invoice | StockCode | Description | Quantity | InvoiceDate | Price | Customer ID | LineAmount |
|---|---|---|---:|---|---:|---:|---:|
| 581483 | 23843 | PAPER CRAFT , LITTLE BIRDIE | 80,995 | 2011-12-09 09:15:00 | 2.08 | 16446 | 168,469.60 |
| C581484 | 23843 | PAPER CRAFT , LITTLE BIRDIE | -80,995 | 2011-12-09 09:27:00 | 2.08 | 16446 | -168,469.60 |

负价格记录：

| Invoice | StockCode | Description | Quantity | Price | LineAmount |
|---|---|---|---:|---:|---:|
| A506401 | B | Adjust bad debt | 1 | -53,594.36 | -53,594.36 |
| A516228 | B | Adjust bad debt | 1 | -44,031.79 | -44,031.79 |
| A528059 | B | Adjust bad debt | 1 | -38,925.87 | -38,925.87 |
| A563186 | B | Adjust bad debt | 1 | -11,062.06 | -11,062.06 |
| A563187 | B | Adjust bad debt | 1 | -11,062.06 | -11,062.06 |

解读：

- `80,995` 与 `-80,995` 是同一客户、同一商品、间隔 12 分钟的一正一负记录，更像大额误下单后快速取消，不应孤立删除。
- 负价格不是商品负价，而是 bad debt adjustment。它应从商品销售和商品价格分析中排除，但在财务对账中保留并单列。
- 零价格也要细分：`Price = 0` 有 6,202 行，其中 `Price = 0 & Quantity < 0` 且非 `C/A` 单有 3,457 行，解释为商品损坏/库存损耗。

## 问题 4：CustomerID 的“沉默大多数”

支持代码：

```python
customer_missing_summary(work)
customer_missing_bucket_summary(work)
invoice_customer_completeness(work)
```

总体对比：

| segment | 行数 | 行数占比 | 金额合计 | 金额占比 | 平均行金额 | 中位行金额 | UK 占比 | 正向销售行 | 损耗行 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Customer ID missing | 243,007 | 22.77% | 2,638,958.18 | 13.68% | 10.86 | 4.98 | 98.77% | 236,122 | 3,457 |
| Customer ID present | 824,364 | 77.23% | 16,648,292.39 | 86.32% | 20.20 | 11.25 | 89.92% | 805,549 | 0 |

缺失群体内部结构：

| bucket | 行数 | 占缺失群体 | 金额合计 |
|---|---:|---:|---:|
| normal positive line: Quantity > 0 and Price > 0 | 236,122 | 97.17% | 3,229,538.96 |
| damage / inventory loss: Price = 0 and Quantity < 0 | 3,457 | 1.42% | 0.00 |
| zero-price positive quantity | 2,674 | 1.10% | 0.00 |
| cancellation / return: C invoice | 750 | 0.31% | -431,531.07 |
| bad debt: A invoice | 6 | 0.00% | -147,614.08 |

Invoice 级别完整性：

| pattern | invoice 数 | 行数 | 金额合计 | DOTCOM POSTAGE invoice | 损耗 invoice | invoice 占比 | 行数占比 |
|---|---:|---:|---:|---:|---:|---:|---:|
| all_missing | 8,752 | 243,007 | 2,638,958.18 | 1,409 | 3,393 | 16.32% | 22.77% |
| all_present | 44,876 | 824,364 | 16,648,292.39 | 16 | 0 | 83.68% | 77.23% |

高频缺失 Customer ID 商品/费用：

| StockCode | Description | 行数 | 金额合计 | Quantity 合计 |
|---|---|---:|---:|---:|
| DOT | DOTCOM POSTAGE | 1,428 | 310,741.11 | 1,422 |
| 85099B | JUMBO BAG RED RETROSPOT | 668 | 11,843.84 | 3,107 |
| 22423 | REGENCY CAKESTAND 3 TIER | 635 | 58,076.95 | 2,680 |
| 21931 | JUMBO STORAGE BAG SUKI | 635 | 14,029.48 | 3,266 |
| 47566 | PARTY BUNTING | 621 | 45,262.27 | 4,775 |

解读：

- `Customer ID` 缺失是结构性缺失，不是随机空值。没有 mixed invoice，说明缺失发生在订单/渠道层面。
- 商品损坏/库存损耗 3,457 行全部缺 Customer ID，但只占缺失群体 1.42%；所以不能写成“缺失 Customer ID 就是损耗”。
- 缺失群体主体仍是正常正向销售，且 UK、DOTCOM POSTAGE、低单行金额更突出。合理推测是匿名线上订单、dotcom/system channel、未绑定客户订单，以及少量库存损耗/系统调整的混合群体。
- 销售报表可以保留这些记录并标记；RFM 客户分群不应把它们混入已识别客户；库存质量分析应单独保留损耗子集。


支持代码：

```python
gross_product_invoice_basket_sizes(work)
product_pair_association_summary(work)
quality_flag_association_summary(work)
invoice_pattern_association_summary(work)
```

### 1. 购物篮规模有长尾，推荐模型不能直接套普通 basket 规则

| 指标 | 数值 |
|---|---:|
| 正向产品销售 invoice 数 | 39,516 |
| 每单唯一商品数中位数 | 15 |
| P90 / P95 / P99 | 51 / 73 / 196.85 |
| 最大每单唯一商品数 | 1,108 |
| 50 个以上唯一商品的 invoice | 4,123（10.43%） |

解读：这不是纯零售小票数据，里面有明显的大 basket/批发式订单。做关联规则或商品推荐时，如果不分层，超大订单会制造大量“同现”组合，拉高 support。商品推荐应至少区分普通订单与 50+ 商品的大订单，或对超大 basket 做降权/截断。

### 2. 商品共购确实存在，但应该看 lift/Kulczynski，不只看 confidence

高 support 的产品对：

| 商品 A | 商品 B | 共现 invoice | support | conf A=>B | conf B=>A | lift | Kulc | 大 basket 占比 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| JUMBO BAG PINK POLKADOT | JUMBO BAG RED RETROSPOT | 1,426 | 3.61% | 63.52% | 35.75% | 6.29 | 49.63% | 36.61% |
| JUMBO STORAGE BAG SUKI | JUMBO BAG RED RETROSPOT | 1,324 | 3.35% | 56.85% | 33.19% | 5.63 | 45.02% | 42.98% |
| RED HANGING HEART T-LIGHT HOLDER | WHITE HANGING HEART T-LIGHT HOLDER | 1,234 | 3.12% | 70.11% | 23.00% | 5.16 | 46.56% | 35.41% |
| LUNCH BAG RED RETROSPOT | LUNCH BAG BLACK SKULL | 1,202 | 3.04% | 39.33% | 51.13% | 6.61 | 45.23% | 41.76% |
| PACK OF 72 RETROSPOT CAKE CASES | 60 TEATIME FAIRY CAKE CASES | 1,197 | 3.03% | 38.39% | 56.28% | 7.13 | 47.33% | 50.04% |

高 lift 且较均衡的产品对多是同系列/同套装：

| 商品 A | 商品 B | 共现 invoice | support | conf A=>B | conf B=>A | lift | Kulc |
|---|---|---:|---:|---:|---:|---:|---:|
| KIDS RAIN MAC BLUE | KIDS RAIN MAC PINK | 171 | 0.43% | 83.01% | 78.44% | 150.47 | 80.73% |
| HERB MARKER THYME | HERB MARKER ROSEMARY | 232 | 0.59% | 93.17% | 92.06% | 146.10 | 92.62% |
| HERB MARKER PARSLEY | HERB MARKER CHIVES | 204 | 0.52% | 81.93% | 92.73% | 147.16 | 87.33% |

解读：这能作为 Q1.3 “商品推荐模型”清洗策略的证据。只用 confidence 会偏向高频商品；加 lift/Kulczynski 后更容易看到同系列商品的真实强关联。但这些结论里 35%-50% 的共现来自 50+ 商品的大 basket，推荐模型需要把大订单单独建模。

### 3. 数据质量标记之间也能用关联规则验证

| 规则/关联 | both rows | conf 左=>右 | conf 右=>左 | lift | 解读 |
|---|---:|---:|---:|---:|---|
| Description missing => Zero price | 4,382 | 100.00% | 70.66% | 172.10 | Description 缺失不是普通文本缺失，几乎绑定零价记录 |
| Description missing <=> Damage/inventory loss | 2,689 | 61.37% | 77.78% | 189.47 | 缺失描述大量来自损耗/盘点语义 |
| Damage/inventory loss => CustomerID missing | 3,457 | 100.00% | 1.42% | 4.39 | 损耗一定缺客户，但缺客户不等于损耗 |
| Cancellation C invoice => Negative quantity | 19,493 | 99.99% | 84.94% | 46.51 | `C` 前缀基本就是负数量退货/取消 |
| Bad debt A invoice => Non-product StockCode | 6 | 100.00% | 0.10% | 175.18 | `A/B` 是低 support 但高价值的 rare pattern |

解读：这个补充支持之前的判断：Q1 中最有价值的不是再找普通空值，而是把缺失、零价、负数量、前缀、StockCode 类型放在同一个规则框架下看。

### 4. 多维关联能进一步定位匿名/dotcom/system channel

| 规则/关联 | both invoice | conf 左=>右 | conf 右=>左 | lift | 解读 |
|---|---:|---:|---:|---:|---|
| DOT invoice => non-product invoice | 1,425 | 100.00% | 25.80% | 9.71 | DOT 本质上是非产品费用/渠道代码 |
| DOT invoice => all CustomerID missing | 1,409 | 98.88% | 16.10% | 6.06 | DOT 与匿名/系统渠道高度绑定 |
| Damage invoice => all CustomerID missing | 3,393 | 100.00% | 38.77% | 6.13 | 损耗 invoice 全部是缺失客户订单 |
| DOT invoice => large basket 50+ | 885 | 62.11% | 21.47% | 8.08 | DOT 常出现在大 basket/线上批量订单中 |
| all CustomerID missing => UK | 8,603 | 98.30% | 17.52% | 1.07 | 缺客户 ID 主要是英国本土渠道问题 |

解读：`Customer ID` 缺失的主因更像 UK dotcom/system/anonymous channel，而不是跨境、退货或单纯 ETL 漏值。这一条可以增强 Q1.2 问题 4 的业务解释。
