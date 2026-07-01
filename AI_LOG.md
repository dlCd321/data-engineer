# AI_LOG.md - AI 对话记录

> 说明：本项目 AI 使用次数较多，完整逐字导出体量很大。这里按题目“如果对话量极大，至少保留最关键的 5-10 次对话”的要求，整理了对最终实现影响最大的关键对话。  
> 其中 Q1、Q4 的部分内容来自当时保留的原始回复；其他模块根据本地项目记忆和最终产物整理为关键回复摘录。没有把这些整理内容冒充为完整逐字聊天导出。

---

## AI 使用统计

| AI 工具 | 大致对话次数 | 主要用途 |
|---|---:|---|
| Codex / ChatGPT | 30+ | 仓库探索、Notebook/脚本实现、Markdown 报告、Debug、测试验证 |
| ChatGPT 网页版 / 其他补全工具 | 10+ | prompt 草稿、思路拆解、表达润色 |

---

## 模块 1：数据质量探索

### 对话 1：Q1.1 - 从基础 EDA 扩展到业务语义（使用工具：Codex）

**Prompt**：

```text
[$data-analysis] 我q1里的notebook还可以探索什么方面
```

**AI 回复关键原文**：

```text
我看了 q1_code.ipynb 和 Q1 题目要求。现在 notebook 还只是基础 EDA，可以往这些方向补，优先级从高到低：

1. 非产品 StockCode 分类
不只是看 value_counts()，要把特殊码分组解释：
- POST / DOT / C2：邮费、dotcom postage、carriage
- D：折扣
- M：manual adjustment
- BANK CHARGES / AMAZONFEE / CRUK：费用/佣金
- gift_0001_*：礼品券

2. 极端 Quantity 不要直接当异常删
最大 80995 和最小 -80995 是同一商品、同一客户、间隔 12 分钟的销售与取消。

3. 负数和 0 价格分开看
- Price < 0 只有 5 行，都是 bad debt adjustment
- Price = 0 有 6,202 行，很多是 lost、damaged、short、check、缺失描述
- Quantity < 0 不全是取消单：有 3,457 行是数字 Invoice + 0 价格，多半是库存损耗/调整

4. Customer ID 缺失群体画像
- 缺失 Customer ID：243,007 行，占 22.77%
- 但金额只占约 13.68%
- 98.77% 来自 UK
- 高频商品里有 DOTCOM POSTAGE，可以推测偏匿名线上/系统渠道/未绑定客户订单

建议 notebook 最后加一个“小结 cell”，把这些探索收敛成 Q1.1 的 5 个以上数据质量问题，并明确哪些应该删除、哪些应该保留、哪些要按下游用途分开处理。当前最缺的是“业务解读”和“清洗策略口径”，不是更多 describe()。
```

**我的验证和修正**：

我没有直接复制 AI 的结论，而是回到 notebook 逐项验证。最后确认：

- `C` invoice 基本是取消/退货；
- `A` invoice 是 bad debt adjustment；
- `Price = 0 & Quantity < 0` 不能当普通退货，很多是 damaged / check / thrown away 等库存损耗；
- `Customer ID` 缺失是订单/渠道层面的结构性缺失，不是随机空值；
- 商品销售、净销售、库存质量、财务对账应该使用不同口径。

这部分最终沉淀到 `q1_data_quality/q1_code.py`、`data_quality_report.md`、`findings.md`、`cleaning_strategy.md`。

---

### 对话 2：Q1.2 - 继续按关联规则挖掘（使用工具：Codex）

**Prompt**：

```text
按照这个规则看看q1还有没有什么能挖出来
```

**AI 回复摘录**：

```text
可以继续从 frequent pattern / association rules 的角度看 Q1，但要先定义正确的 basket。

建议不要直接用所有行，而是使用 IsGrossProductSale=True 的 invoice 级唯一商品 basket。否则 C 发票、DOT/POST、坏账、库存损耗都会污染商品共现结果。

可以补四类结果：
1. basket size 分布，识别大 basket / 批发式订单；
2. product-pair support / confidence / lift / Kulczynski；
3. 数据质量标记之间的关联，例如 Description missing、Zero price、Damage/inventory loss、CustomerID missing；
4. invoice pattern 之间的关联，例如 C invoice 与 negative quantity、A invoice 与 bad debt。

如果 mlxtend 不可用，用 pandas + Counter + combinations 也能实现。
```

**我的验证和修正**：

这次我接受了 AI 的方向，但实现时没有依赖 `mlxtend`，而是在脚本里用 `Counter` / `combinations` 做可复现统计。最终发现：

- 正向商品销售 invoice 的唯一商品数中位数为 15，但 P95 到 73，存在明显大 basket；
- 高 lift 产品对多为同系列商品；
- `Description missing => Zero price`、`Damage/inventory loss => CustomerID missing` 等规则能反向验证 Q1 的清洗口径；
- 大 basket 会放大商品共现，需要在推荐模型中降权或分层。
  这次的挖掘主要是想挖出一些 customer id 的东西，然后有意外发现：如果 description 缺失的话，它更大概率是没有 price 的。这也印证了我们的发现：当 price 等于 0、quantity 小于等于 0 的时候，description missing 很多时候就是因为仓库数据或库存的缺失。

---

## 模块 2：SQL 与业务分析



### 对话 1：Q2 - ER 图代码（使用工具：Codex）

**Prompt**：

```text
这个数据库的erdiagram给我代码
```

**AI 回复摘录**：

```text
可以用 Mermaid erDiagram 表达 9 张 Olist 表：

- CUSTOMERS -> ORDERS
- ORDERS -> ORDER_ITEMS
- ORDERS -> ORDER_PAYMENTS
- ORDERS -> ORDER_REVIEWS
- PRODUCTS -> ORDER_ITEMS
- SELLERS -> ORDER_ITEMS
- PRODUCT_CATEGORY_NAME_TRANSLATION -> PRODUCTS
- GEOLOCATION 只能作为 zip prefix 的逻辑关联，不应画成严格主外键。
```

**我的验证和修正**：

我把图单独放到 `q2_sql_analysis/erdiagram.md`。对 `geolocation` 我没有强行画严格外键，因为 zip prefix 在 Olist 数据里不是干净的一对一维表，这一点比图画得复杂更重要。
画这个图方便我修改一些join语句等

---

## 模块 3：ETL Pipeline

### 对话 1：Q3 - 复用 Q1 语义设计 ETL（使用工具：Codex）

**Prompt**：

```text
q3的应该怎么implement
```

**AI 回复摘录**：

```text
Q3 不应该重新发明一套清洗规则，应该复用 Q1 已验证的业务语义：

1. C invoice 是 cancellation / return；
2. A invoice 是 bad debt adjustment；
3. Price=0 且 Quantity<0 的数字 invoice 多为 damage / inventory loss；
4. 非产品 StockCode 应该分桶，而不是混入商品销售；
5. Customer ID 缺失行可以进入 sales facts，但不能进入 customer features。

建议 pipeline.py 拆成：
load_data -> normalize_columns -> classify_stock_code -> classify_retail_rows -> build_sales_facts -> build_customer_features -> build_returns_log -> validate_outputs -> write_validation_report。

退货匹配使用保守规则：same customer、same stock_code、abs(quantity) 相同、原销售早于退货、选择最近一笔 prior sale。匹配不到就保留 unmatched，不要强行猜。
```

**我的验证和修正**：

我最终实现时保留了“保守可解释”的匹配策略。`validation_report.md` 显示：

- 输入 1,067,371 行；
- `sales_facts` 1,036,877 行；
- `customer_features` 5,852 行；
- `returns_log` 19,494 行；
- eligible return 匹配率 36.30%；
- 运行时间约 2.20 秒，峰值内存约 876.66 MB。

我没有为了提高匹配率去匹配 partial return / split return，因为那会让规则变得难解释，也更容易在面试追问时说不清楚。

---

## 模块 4：LLM 抽取

### 对话 1：Q4 - 初始 pipeline 设计（使用工具：ChatGPT / Codex）

**Prompt**：

```text
你是一名数据工程师，正在完成一个 LLM 文本抽取模块的设计文档。

请根据以下任务背景，帮我撰写 pipeline_design.md，字数控制在 300-500 中文字，语言专业、清晰、像笔试提交文档，不要写得像 AI 生成。

任务背景：
- 数据表：Olist order_reviews
- 字段：review_id, review_score, review_comment_message
- 处理对象：评分 ≤ 3 分的葡萄牙语差评，约 1-2 万条
- 目标：从非结构化评价文本中抽取结构化问题信息
- 输出字段包括 review_id、issues.category、issues.severity、evidence_quote、evidence_quote_en、sentiment_score、actionable_for_seller、confidence

约束：
- 总成本不超过 3 USD
- 总耗时不超过 40 分钟
- 不能所有评论都直接丢给大模型
- 很多评论只有 “ruim”“péssimo” 等短文本，需要用规则处理
- 必须避免 LLM 编造原文中不存在的问题
```

**AI 回复关键原文**：

```text
本模块仅处理 order_reviews 中 review_score <= 3 且存在有效 review_comment_message 的差评文本，目标是在成本和耗时受限下抽取可用于卖家改进的问题信息。整体流程采用“规则优先、LLM 补充”的分流设计，避免将全部评论直接提交给大模型。

首先对评论做基础清洗，包括去除空值、纯空格、重复文本和明显无信息文本。对于 “ruim”“péssimo”“não gostei”“bom”等短文本，只保留情绪判断，不强行生成具体问题类别，默认归为 other 或仅输出低置信度结果。对于包含明显关键词的评论，使用规则直接映射类别。

只有长度较长、包含多个问题或规则无法稳定判断的评论进入 LLM。LLM 直接处理葡萄牙语原文，并在同一次输出中生成 evidence_quote_en，不额外调用翻译模型。Prompt 明确要求模型只能基于原文证据抽取，不允许推测订单状态、商品类型或卖家责任；evidence_quote 必须来自原文，输出严格 JSON。
```

**我的验证和修正**：

这个回答提供了框架，但还不够工程化。我后面把流程改成：

```text
Filter score<=3
-> Normalize Text
-> Deduplicate
-> Rule Engine
-> Small LLM batch
-> Large LLM single / selective retry
-> Merge Results
-> Map Back to review_id
-> Structured JSON
```

关键修正是：小评论不一定没价值，短但有信息的评论可以 batch 到便宜模型；复杂长评论或低置信样本再进入大模型。

---

### 对话 2：Q4 - 真实 DeepSeek/OpenRouter 路径与 JSON schema（使用工具：Codex）

**Prompt**：

```text
我只用deepseek或者open router模型
真正定位
```

**AI 回复摘录**：

```text
不能只看 offline fallback 输出判断 live route 是否正常。要直接复现 provider 路径。

DeepSeek / OpenRouter 可以用 OpenAI-compatible client：
- OpenRouter base_url = https://openrouter.ai/api/v1
- DeepSeek base_url = https://api.deepseek.com

CLI 应该暴露 --provider、--small-model、--large-model、--live-sample-size 等参数，不要把模型写死。

另外 DeepSeek JSON mode 有一个坑：如果 response_format={"type":"json_object"}，prompt 本身必须包含 json 这个词，否则可能返回 HTTP 400：Prompt must contain the word 'json'。
```

**我的验证和修正**：

我把 `prompt_template.txt`、`extract_reviews.py` 和 CLI 参数对齐，最后用 DeepSeek 做了 full live 验证。结果写进 `q4_llm_extraction/cost_report.md`：

- Provider: DeepSeek；
- Small model: `deepseek-v4-flash`；
- Large model: `deepseek-v4-pro`；
- 低分评论数 22,754；
- 空文本 8,117；
- 去重后文本数 13,592；
- 实际耗时 47 分钟；
- 实际账单 14 RMB；
- LLM 调用 2,259 次；
- LLM 失败 214 次；
- schema 校验失败 118 次；
- evidence 校验失败 83 次。

成本低于 $3，但 47 分钟超过了 40 分钟约束，所以我在报告里没有写成“完全满足限制”，而是写成“成本满足，时间还需要进一步压缩”。

---

### 对话 3：Q4 - 没有 ground truth 怎么验证（使用工具：Codex）

**Prompt**：

```text
你没有 ground truth，怎么验证抽取得对？
所以我的指标呢，我叫你算指标
能不能fold validation一下
3 repeated 30-sample validation batches 帮我实现
```

**AI 回复摘录**：

```text
这里不应该叫传统 k-fold validation，因为没有训练模型和训练/验证划分。更准确的说法是 repeated validation batches。

可以从 live full run 输出中按 method 分层抽样：
- Rule Engine 30 条；
- Small LLM 30 条；
- Large LLM 30 条；
再切成 3 个 batch，每个 batch 30 条，且每个 batch 都有 10 条 rule、10 条 small_llm、10 条 large_llm。

指标包括：
- classification accuracy；
- evidence compliance；
- omission / miss rate；
- hallucination rate；
- actionable accuracy。

不要只写方法，要把 90 条样本的计数和比例写进 accuracy_evaluation.md。
```

**我的验证和修正**：

最终 `accuracy_evaluation.md` 写入了真实指标：

- 分类准确率：80 / 90 = 88.9%；
- evidence 合规率：105 / 114 = 92.1%；
- 漏召回率：13 / 115 = 11.3%；
- 幻觉率：6 / 114 = 5.3%；
- actionable 判断准确率：86 / 90 = 95.6%。

这个结果说明主要问题不是 LLM，而是 Rule Engine 过度触发关键词。后续优化应该先改规则层，而不是盲目升级模型。

---

## 模块 5：系统设计

### 对话 1：Q5 - 实时数据管道设计（使用工具：Codex）

**Prompt**：

```text
q5怎么实现
```

**AI 回复摘录**：

```text
Q5 不应该只列 Kafka / Flink / ClickHouse 技术栈，而要逐项回答题面：
1. 架构图；
2. 存储选型；
3. LLM 成本控制；
4. 三个最大风险点和预案；
5. 10 万订单/天到 100 万订单/天的变化。

可以把交易系统作为 OLTP 事实源，用 outbox + CDC 推送 Kafka；Flink 做订单状态、物流报警和评价文本处理；Redis 承接热状态；ClickHouse 承接历史查询和聚合；S3/MinIO 保留原始事件用于审计和重放。

Q4 的真实运行数据可以支撑 Q5 的 LLM 成本控制：14 RMB、47 分钟、2259 次调用、214 次失败，说明生产方案必须有规则分流、去重、缓存、预算 gate 和降级策略。
```

**我的验证和修正**：

我把模板重写成 `q5_system_design/real_time_pipeline_design.md`，包含 Mermaid 架构图、存储层解释、LLM 成本估算、风险预案和扩容策略。这里我主要修改的是表达方式：不是“用了哪些技术”，而是“为什么每层存在，以及约束下怎么降级”。

---

## 加分题：AI 协作分析（Q6.1）

### 选定题目：Q1 数据质量探索与清洗策略

我选择 Q1 作为 AI 协作反向分析，因为 Q1 最容易出现“AI 看起来答得很完整，但实际业务口径不准确”的问题。

### 第 1 次 Prompt

```text
[$data-analysis] 我q1里的notebook还可以探索什么方面
```

**AI 回复核心**：

```text
继续探索特殊 StockCode、极端 Quantity、Price < 0、Price = 0、Customer ID 缺失、重复行、Description 缺失、时间范围不完整等问题。重点不是更多 describe()，而是业务解读和清洗策略口径。
```

**AI 答案的问题**：

AI 给了方向，但没有强制区分：

- 销售口径；
- 库存损耗口径；
- 财务对账口径；
- 客户分群口径。

如果直接照抄，容易把所有负数量都归为退货，也容易把 `Price=0 & Quantity<0` 的库存损耗写成普通异常值。

### 第 2 次 Prompt

```text
这里补一部分到notebook然后开始实现计划
```

**AI 回复核心**：

```text
把 Q1 notebook 的发现正式落到 q1_code.py 和 Markdown 交付物中。新增派生字段：
- InvoicePrefix
- LineAmount
- IsCancellation
- IsBadDebtAdjustment
- IsDamageOrInventoryLoss
- IsCustomerMissing
- StockCodeCategory

然后输出 data_quality_report.md、findings.md、cleaning_strategy.md。
```

**我的修正**：

我最后把 `IsDamageOrInventoryLoss` 单独做成字段，并在报告中明确：

- 这类记录不进入 gross product sales；
- 但应进入库存/运营质量分析；
- 不能简单 drop。

### 最终结论

- **总迭代次数**：约 3 轮关键迭代。
- **最终代码 vs AI 原始答案的核心差异**：最终代码不是简单异常值清洗，而是按业务语义分层，分别输出销售、退货、库存损耗、财务对账、客户分析口径。
- **如果再做一次，第一个 prompt 会怎么写**：我会直接要求 AI 按“验证查询、业务语义、适用分析口径、不能删除的异常、容易误判点”输出 checklist，而不是只问“还能探索什么”。

更完整的 Q6.1 反思见 `bonus/q6_1_ai_collaboration.md`。

---

## 整体反思

### AI 帮助最大的题

AI 帮助最大的是 Q1、Q5：

- Q1：帮我把基础 EDA 扩展成业务语义问题清单；
- Q5：帮我把系统设计从“技术栈列表”改成有 SLA、成本、风险和扩容逻辑的设计稿。

### AI 几乎帮不上忙的部分

AI 不能直接替我判断真实数据结果，尤其是：

- Q1 的异常值到底是不是业务合理；
- Q2 SQL 在本地 MySQL 的真实执行计划；
- Q4 full live 的真实账单、失败率、schema/evidence 错误；
- Q3 退货匹配率是否合理。

这些都必须跑代码、查数据、看输出，不能靠 AI 猜。

### 我识别 AI 错误答案的方法

1. 对照题目 README，看 AI 是否漏掉强制要求，例如 MySQL 8.0、Q4 成本/时间限制、Q5 字数和架构要求。
2. 跑脚本和测试，而不是只看回答是否顺眼。
3. 对关键指标做 sanity check，例如 Q1 金额口径、Q2 join 后 SUM 是否翻倍、Q4 route/method 分布是否合理。
4. 对 AI 给出的设计追问边界条件，例如 Q3 partial return 为什么不匹配、Q4 为什么不能每条都大模型。

### 一句话总结

AI 最适合帮我列验证路径、生成初稿和暴露遗漏；最终结论必须回到真实数据、运行结果和题目约束里验证。
