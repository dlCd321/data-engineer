# AI_LOG.md - AI 完整对话记录

> 请粘贴你和 AI 的**完整对话记录**（**原文，不要删改、不要总结**）。
> 
> 📌 **填写要求**：
> - 每段对话必须标注：对应**哪道题**、**第几次迭代**、**用了什么 AI**
> - 截图也可以（放在 `ai_logs/` 子目录下并在此处引用）
> - 不需要美化排版 —— 我们就是要看原始过程
> 
> ⚠️ **重要**：
> - 谎报 AI 使用情况、伪造对话记录 → 在面试中会被发现 → **直接淘汰**
> - 完全没用 AI 也没关系，请在此说明
> - 如果对话量极大，至少保留**最关键的 5-10 次对话**

---

## 📊 AI 使用统计

请简要统计你的 AI 使用情况：

| AI 工具   | 大致对话次数 | 主要用途                  |
|---------|--------------|-----------------------|
| codex   | ~30 次 | 代码生成、Debug            |
| chatgpt | ~50 次自动补全 | 项目路径探索，prompt设计， 环境配置 |

---

## 🔍 模块 1：数据质量探索

### 对话 1：Q1.1 - 数据加载与初探（使用工具：codex）

**Prompt**：
```
[$data-analysis] 我q1里的notebook还可以探索什么方面
```

**AI 回复**：
```
我看了 [q1_code.ipynb](/Users/bruce/PycharmProjects/data-engineer/q1_data_quality/q1_code.ipynb) 和 Q1 题目要求。现在 notebook 还只是基础 EDA，可以往这些方向补，优先级从高到低：


1. **非产品 StockCode 分类**
   不只是看 `value_counts()`，要把特殊码分组解释：
   - `POST` / `DOT` / `C2`：邮费、dotcom postage、carriage
   - `D`：折扣
   - `M`：manual adjustment
   - `BANK CHARGES` / `AMAZONFEE` / `CRUK`：费用/佣金
   - `gift_0001_*`：礼品券
   - 这些特殊码共 6,094 行，占约 `0.57%`，金额占比约 `-0.49%`

2. **极端 Quantity 不要直接当异常删**
   最大 `80995` 和最小 `-80995` 是同一商品、同一客户、间隔 12 分钟的销售与取消：
   - `581483 / 23843 / 80995`
   - `C581484 / 23843 / -80995`
   这可以作为“看起来异常，但其实有业务解释”的强案例。

3. **负数和 0 价格分开看**
   - `Price < 0` 只有 5 行，都是 bad debt adjustment
   - `Price = 0` 有 6,202 行，很多是 `lost`、`damaged`、`short`、`check`、缺失描述
   - `Quantity < 0` 不全是取消单：有 3,457 行是数字 Invoice + 0 价格，多半是库存损耗/调整

4. **Customer ID 缺失群体画像**
   这个是 Q1.2 的重点。你可以补：
   - 缺失 Customer ID：243,007 行，占 `22.77%`
   - 但金额只占约 `13.68%`
   - 98.77% 来自 UK
   - 平均行金额 `10.86`，有 Customer ID 的是 `20.20`
   - 高频商品里有 `DOTCOM POSTAGE`，可以推测偏匿名线上/系统渠道/未绑定客户订单

5. **重复行是否真重复**
   现在只算了 `duplicated()`。可以进一步说明：
   - 精确重复行有 34,335 行
   - 但数据没有 invoice line id，同一订单同一商品可能真实出现多行
   - 所以不能无脑 drop duplicate，要看下游用途决定

6. **Description 和 StockCode 的错配**
   很值得写进“非显而易见问题”：
   - 有些 `StockCode` 对应多个描述
   - 说明 Description 混入了库存/人工备注，不总是商品名

7. **缺失 Description 的业务含义**
   缺失 Description 有 4,382 行，而且：
   - `Price` 全部是 0
   - `Customer ID` 全部缺失
   - 约 61% 是负 Quantity
   这比单纯说“Description 有缺失”强很多。

8. **时间范围和月度可比性**
   数据到 `2011-12-09`，所以 2011 年 12 月不是完整月份。后续如果做月度趋势，不能直接把 2011-12 和其他完整月份比较。

建议 notebook 最后加一个“小结 cell”，把这些探索收敛成 Q1.1 的 5 个以上数据质量问题，并明确哪些应该删除、哪些应该保留、哪些要按下游用途分开处理。当前最缺的是“业务解读”和“清洗策略口径”，不是更多 `describe()`。
```

**你的评估**：
> 我自己写了基础的notebook and Describe然后发现数据里面有很多异常值，然后我开始一个月看根据AI的回复，首先我看了invoice然后发现很多是负的，然后我去官网看了看，发现前缀是C的，invoice说明的是退货或者退订单etc.。然后我开始按照AI给的提示去Notebook里面一个一个看，也会结合的去看，比如说结合quantity还有price。

---

### 对话 2：Q1.2 问题 1 - InvoiceNo 前缀分析（使用工具：____）

**Prompt**：
```

```

**AI 回复**：
```

```

**你的评估**：

---

（按需添加更多对话，每道题至少 1-3 次关键对话）

---

## 📊 模块 2：SQL 与业务分析

### 对话 1：

**Prompt**：

**AI 回复**：

**你的评估**：

---

## 🔄 模块 3：ETL Pipeline

### 对话 1：退货匹配规则讨论（这道题的关键）

**Prompt**：

**AI 回复**：

**你的评估**：
> AI 给的匹配规则有什么漏洞？你怎么修正的？

---

## 🤖 模块 4：LLM 抽取

### 对话 1：Prompt 设计

**Prompt**：你是一名数据工程师，正在完成一个 LLM 文本抽取模块的设计文档。

请根据以下任务背景，帮我撰写 `pipeline_design.md`，字数控制在 300-500 中文字，语言专业、清晰、像笔试提交文档，不要写得像 AI 生成。

任务背景：
 \- 数据表：Olist `order_reviews`
 \- 字段：`review_id`, `review_score`, `review_comment_message`
 \- 处理对象：评分 ≤ 3 分的葡萄牙语差评，约 1-2 万条
 \- 目标：从非结构化评价文本中抽取结构化问题信息
 \- 输出字段包括：
  \- review_id
  \- issues.category
  \- issues.severity
  \- issues.evidence_quote
  \- issues.evidence_quote_en
  \- sentiment_score
  \- actionable_for_seller
  \- confidence

可选问题类别：
 delivery_late, wrong_product, quality_defect, missing_item, seller_communication, packaging, other

约束：
 \- 总成本不超过 3 USD
 \- 总耗时不超过 40 分钟
 \- 不能所有评论都直接丢给大模型
 \- 很多评论只有 “ruim”“péssimo” 等短文本，需要用规则处理
 \- 必须避免 LLM 编造原文中不存在的问题

请在文档中说明以下决策：

1. 分流策略：先过滤空评论、短评论、关键词明显评论；只有复杂长文本才进入 LLM。
2. 葡萄牙语处理：LLM 直接理解葡萄牙语并同时输出英文翻译，不单独调用翻译模型。
3. Prompt 设计：要求 LLM 只基于原文证据抽取，输出严格 JSON，不允许推测。
4. 批处理策略：多条评论合并成一个 batch 请求，降低请求开销和 token 成本。
5. 成本控制：限制输入长度、限制 issues 数量、优先规则抽取、只处理评分 ≤ 3 的有效文本。
6. 质量评估：人工抽样 30 条评论标注，与模型结果比较 category、severity、evidence_quote、actionable_for_seller，并记录错误案例。

输出要求：
 \- 文件标题为：# Pipeline Design
 \- 只输出正文，不要解释你怎么写
 \- 不要使用太夸张的措辞
 \- 内容要像真实工程设计，不要空泛
 \- 字数 300-500 中文字

**AI 回复**：**Pipeline Design**

本模块仅处理 `order_reviews` 中 `review_score <= 3` 且存在有效 `review_comment_message` 的差评文本，目标是在成本和耗时受限下抽取可用于卖家改进的问题信息。整体流程采用“规则优先、LLM 补充”的分流设计，避免将全部评论直接提交给大模型。

首先对评论做基础清洗，包括去除空值、纯空格、重复文本和明显无信息文本。对于 “ruim”“péssimo”“não gostei”“bom”等短文本，只保留情绪判断，不强行生成具体问题类别，默认归为 `other` 或仅输出低置信度结果。对于包含明显关键词的评论，使用规则直接映射类别，例如 `não recebi` 对应 `missing_item` 或配送未完成，`atraso` 对应 `delivery_late`，`quebrado`、`defeito` 对应 `quality_defect`，从而减少 LLM 调用量。

只有长度较长、包含多个问题或规则无法稳定判断的评论进入 LLM。LLM 直接处理葡萄牙语原文，并在同一次输出中生成 `evidence_quote_en`，不额外调用翻译模型。Prompt 明确要求模型只能基于原文证据抽取，不允许推测订单状态、商品类型或卖家责任；`evidence_quote` 必须来自原文，输出严格 JSON，并限制每条评论最多返回 2 个 issues。

按 1-2 万条差评估算，实际进入 LLM 的应为少量复杂样本，总成本控制在 3 USD 内，总耗时控制在 40 分钟内。

质量评估采用人工抽样 30 条评论进行标注，对比 `category`、`severity`、`evidence_quote`、`actionable_for_seller` 和 `confidence`。重点记录错误案例，包括类别误判、证据引用不完整、把情绪词误判为具体问题、以及模型推测原文不存在的信息，并据此迭代关键词规则和 Prompt。

**你的评估**：这是我自己设计的q4 pipeline
order_reviews
      │
      ▼
Filter (score<=3)
      │
      ▼
Normalize Text
      │
      ▼
Deduplicate
      │
      ▼
Review Classification
      │
 ┌────┴───────────────┐
 │                    │
 │ Rule Engine        │ 固定模板评论
 │                    │
 └────┬───────────────┘
      │
      ▼
Small LLM
(短但有信息)
      │
      ▼
Large LLM
(复杂长评论)
      │
      ▼
Merge Results
      │
      ▼
Map Back to review_id
      │
      ▼
Structured JSON
我先用test脚本测试了，数据有很多重复也有很多很短的，我先设计一个normal text.py,hash数据结构这一步跟大模型给的答案一样,然后我优化了一下小的评论也可以有有用的信息，这在我设计的pipeline有体现。然后我觉得小的review可以通过一个batch塞进费用没有那么高的模型里面。大的评论可以塞进一个大一点的模型里面，然后再通过脚本merge result。

最后我用 DeepSeek 跑了一次 full live 验证，Small model 是 `deepseek-v4-flash`，Large model 是 `deepseek-v4-pro`。这次实际用时 47 分钟，账单成本 14 RMB。成本比预期可控，但时间超过了 40 分钟约束，主要原因是 full live 没有限制本地预算 gate，而且 LLM 失败、schema 校验失败和 evidence 校验失败会触发额外 fallback 处理。这个结果让我意识到 Q4 不能只说“用了便宜模型”，还必须把分流比例、失败样本和真实账单写进报告。

---

## 🏗️ 模块 5：系统设计

### 对话 1：

（按上述格式填写）

---

## ⭐ 加分题：AI 协作分析（Q6.1）

> 这部分是单独的加分题，需要选一道你认为最难的题，详细记录 AI 协作过程。
> 请详细参考 README.md 中 Q6.1 的要求。

### 选定的题目：________

### 第 1 次 Prompt

**你的 Prompt**：
```

```

**AI 回复**：
```

```

**AI 答案的问题**：
> 你发现了什么不对的地方？

### 第 2 次 Prompt（迭代修正）

**你的 Prompt**（说明你做了什么调整）：
```

```

**AI 回复**：
```

```

### ...（按需继续迭代）

### 最终结论

- **总迭代次数**：__
- **最终代码 vs AI 原始答案的核心差异**：
- **如果再做一次，你的第一个 prompt 会怎么写**：

---

## 📌 整体反思

### 你在哪些题上 AI 帮助最大？

（请填写）

### 你在哪些题上 AI 几乎帮不上忙？

（请填写）

### 你识别 AI 错误答案的方法是？

> 比如：跑代码验证、对照数据、对照文档、凭经验觉得不对...

（请填写）

### 一句话总结你的 AI 使用心得

（请填写）

---

**注：如果你的对话记录主要是截图，请在此目录创建 `ai_logs/` 子目录存放截图，并在本文档中引用：**

```markdown
![Q3.1 退货匹配讨论](./ai_logs/q3_returns_matching_1.png)
```
