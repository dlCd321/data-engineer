# Q4 低分评论问题抽取 Pipeline 设计

本文档描述针对 Olist `order_reviews` 表的低分评论结构化抽取流程。核心思路是把 Q4 做成一个“可控成本的路由系统”：先过滤低分评论，再标准化、去重和分流；高确定性的模板评论走规则，短但有信息的评论按 batch 交给 Small LLM，复杂长评论或低置信度结果才单条升级到 Large LLM。这样既能控制成本，又能保留复杂差评中的多问题信息。

## 流程总览

```text
order_reviews
      |
      v
Filter (review_score <= 3)
      |
      v
Build raw_text + normalized_text
      |
      v
Deduplicate
      |
      v
Review Classification
      |
      +--> Rule Engine
      |        |
      |        v
      |   Validate Schema
      |
      +--> Small LLM Batch Builder
      |        |
      |        v
      |   Small LLM Batch Call
      |        |
      |        v
      |   Validate Schema + Confidence Check
      |        |
      |        +--> pass
      |        |
      |        +--> fail item -> Large LLM Single Call
      |
      +--> Large LLM Single Call
               |
               v
          Validate Schema
               |
               v
          Merge Results
               |
               v
          Map Back to review_id
               |
               v
          Structured JSON
```

## 1. 输入数据

输入表为 `olist_order_reviews_dataset.csv` 对应的 `order_reviews`，核心字段包括：

| 字段 | 用途 |
|---|---|
| `review_id` | 最终结果回写和追踪的主键 |
| `order_id` | 后续可关联订单、商品、物流信息 |
| `review_score` | 只保留 `<= 3` 的低分评论 |
| `review_comment_title` | 与正文合并后作为评论文本 |
| `review_comment_message` | 主要抽取对象 |
| `review_creation_date` / `review_answer_timestamp` | 可用于后续时间分析，不参与主分类 |

只处理 `review_score <= 3` 的评论。高分评论不进入本流程，因为本题关注差评中的问题原因抽取，处理高分评论会增加成本并稀释分析目标。

## 2. 文本标准化

对标题和正文先生成两份文本，而不是只保留清洗后的版本：

| 字段 | 用途 |
|---|---|
| `raw_text` | 原始标题 + 正文，用于 evidence、人工复核和避免语义丢失 |
| `normalized_text` | 小写、去重音、去标点、压缩空白后用于去重和规则匹配 |

清洗步骤：

1. 合并 `review_comment_title` 与 `review_comment_message`。
2. 去除首尾空格、重复空白、换行和不可见字符。
3. 去除葡萄牙语重音，让 `não` 与 `nao` 进入同一个 dedup key。
4. 去除明显无业务含义的 URL、HTML 标签和标点差异。
5. 保留 `raw_text` 给 LLM 做证据引用，`normalized_text` 只用于工程处理。

设计原则是“标准化只服务工程匹配，不替代原文”。例如 `não recebi o produto` 的 `raw_text` 必须保留给 LLM 和 evidence；`normalized_text` 可以去重音为 `nao recebi o produto` 来减少重复调用。

## 3. 去重策略

去重分两层：

| 层级 | 方法 | 目的 |
|---|---|---|
| 精确去重 | `normalized_text` 计算 hash | 同一句评论只调用一次规则或模型 |
| 近似去重 | 可选使用相似度阈值，例如 token set ratio | 合并大量模板化短评 |

去重后保留一张映射表：

```json
{
  "dedup_key": "hash_of_normalized_text",
  "representative_raw_text": "Não recebi o produto",
  "representative_normalized_text": "nao recebi o produto",
  "records": [
    {
      "review_id": "r1",
      "order_id": "o1",
      "review_score": 1
    },
    {
      "review_id": "r2",
      "order_id": "o2",
      "review_score": 1
    }
  ]
}
```

模型只处理代表文本，最后再把结果映射回所有 `review_id`。这一步是成本控制的关键，因为差评中常见大量重复短句，例如 `ruim`、`péssimo`、`não recebi o produto`。

## 4. 评论分流策略

去重后的评论进入 `Review Classification`。这里不是 `Rule Engine -> Small LLM -> Large LLM` 的顺序流水线，而是一个路由分支：每条评论优先只走一条主路径，只有失败或低置信度时才升级。

| 路径 | 触发条件 | 处理方式 |
|---|---|---|
| Rule Engine | 空评论、极短评论、高频模板、明确关键词 | 不调用模型，直接生成结构化结果 |
| Small LLM | 5 到 80 个词、信息明确、通常只有一个主问题 | 按 token budget batch 调用，低成本抽取单个或少量 issue |
| Large LLM | 超过 80 个词、多问题、时间线复杂、Small LLM 失败 | 不做 batch，单条评论调用，抽取多标签、多问题和证据 |

### 4.1 Rule Engine：固定模板和低信息评论

适用条件：

- 文本为空或只有标题。
- 字数极短，例如 `ruim`、`péssimo`、`horrível`。
- 只有情绪判断但没有原因，例如 `não gostei`、`não recomendo`。
- 命中高置信度模板，例如：
  - `não recebi o produto` -> `delivery.not_received`
  - `produto com defeito` -> `product.defective`
  - `produto errado` -> `product.wrong_item`
  - `demora na entrega` -> `delivery.delay`
  - `não recomendo` -> `general.negative_low_detail`

规则引擎直接输出结构化结果，不调用 LLM。规则结果需要带上 `method = "rule"` 和 `confidence`，便于后续评估和抽样复核。

低信息差评不强行猜原因，统一进入 `general.negative_low_detail`。这比让模型编造“可能是物流问题”更可靠。

### 4.2 Small LLM：短但有信息的评论

适用条件：

- 评论长度较短，例如 5 到 80 个词。
- 有明确业务信息，但规则不能稳定覆盖。
- 通常只包含 1 个主要问题。

示例：

```text
o produto chegou quebrado e a loja nao respondeu
```

Small LLM 的任务是低成本分类，不做过度推理。短评论 token 少、结构相似，适合多个 `dedup_key` 组成一个 batch 一起请求。输出必须严格遵守 JSON schema，并从 `raw_text` 中截取 evidence，避免模型编造问题。

### 4.3 Large LLM：复杂长评论

适用条件：

- 评论较长，例如超过 80 个词。
- 同时提到多个问题，例如物流延迟、商品损坏、客服不回应。
- 语义复杂，包含转折、否定或时间线。
- Small LLM 低置信度，例如 `confidence < 0.7`。
- Small LLM 输出不符合 schema。
- Small LLM 的 evidence 无法在原文中找到。

Large LLM 负责多标签、多问题抽取。长评论不做 batch，而是每条代表评论单独调用；这样可以避免多条复杂评论之间互相干扰，也更容易校验 evidence 和定位失败样本。Large LLM 可以输出多个 `issues`，并为每个问题给出类别、证据片段和置信度。

## 5. Batch 策略

本 pipeline 的 batch 只用于短评论和本地规则，不用于复杂长评论。

| 对象 | 是否 batch | 原因 |
|---|---|---|
| Rule Engine | 是，本地批量处理 | 规则匹配没有模型成本，可以一次处理整批去重文本 |
| Small LLM | 是，按 `route + token_budget` 组批 | 短评论语义简单、token 少，批量请求可以减少 API 请求次数和固定开销 |
| Large LLM | 否，单条处理 | 长评论通常包含多个问题、时间线和转折，batch 后容易互相污染，也更难做 evidence 对齐 |

Small LLM batch 的输入使用 JSON 数组，每条记录都带 `dedup_key`，模型返回时也必须按 `dedup_key` 对齐：

```json
[
  {
    "dedup_key": "hash_001",
    "raw_text": "Produto chegou quebrado"
  },
  {
    "dedup_key": "hash_002",
    "raw_text": "A loja nao respondeu"
  }
]
```

batch 构造规则：

1. 只把 Small LLM 路径的短评论放进 batch。
2. 每个 batch 控制总 token，避免超过上下文窗口。
3. 不把不同路径的评论混在同一个 batch。
4. 每条输出必须带 `dedup_key`，便于和原始评论映射。
5. 如果 batch 中只有部分记录 schema 错误，只重试失败的 `dedup_key`；如果整批 JSON 解析失败，则拆小 batch 后重试。

Large LLM 不使用 batch。原因是长评论常常一条评论里就有多个 issue，如果把多条长评论放进同一个 prompt，模型容易遗漏、串证据或把 A 评论的问题归到 B 评论。单条调用虽然请求次数更多，但 Large LLM 样本占比预计只有 5%-10%，总体成本仍可控。

## 6. 问题分类体系

建议使用稳定的层级化标签，避免自由文本类别失控：

| 一级类别 | 二级类别示例 | 含义 |
|---|---|---|
| `delivery` | `delay`, `not_received`, `tracking_issue` | 物流延迟、未收到货、物流信息异常 |
| `product` | `defective`, `wrong_item`, `poor_quality`, `missing_parts` | 商品损坏、发错货、质量差、缺件 |
| `service` | `no_response`, `refund_problem`, `seller_attitude` | 客服、退款、商家沟通问题 |
| `payment` | `billing_issue`, `refund_delay` | 支付或退款到账问题 |
| `general` | `negative_low_detail`, `unclear` | 负面但信息不足，或无法判断 |

## 7. Schema 校验和结果合并

所有路径输出后都先进入 `Validate Schema`，再进入 `Merge Results`。校验规则包括：

1. 输出必须是合法 JSON。
2. `category` 和 `subcategory` 必须来自预定义标签体系。
3. `evidence` 必须能在 `raw_text` 中找到，不能是翻译后重新生成的句子。
4. `confidence` 必须在 0 到 1 之间。
5. `issues` 不能为空；如果无法判断，使用 `general.unclear` 并标记 `needs_manual_review = true`。

合并规则：

1. Rule Engine 结果直接进入最终结果。
2. Small LLM 结果如果 `confidence >= 0.7` 且 JSON 合法，则接受。
3. Small LLM batch 中通过校验的记录直接接受。
4. Small LLM batch 中低置信度、schema 错误或 evidence 不在原文中的单条记录，单独升级到 Large LLM。
5. Large LLM 结果仍低置信度时，标记为 `needs_manual_review = true`。

合并时不覆盖 `review_id` 维度，而是先在去重文本维度保存结果，再通过映射表回填到原始评论。

## 8. 映射回 review_id

每个去重代表文本可能对应多个原始 `review_id`。最终展开时，每个 `review_id` 都得到一份结构化记录：

```json
{
  "review_id": "abc123",
  "order_id": "order456",
  "review_score": 1,
  "raw_text": "Não recebi o produto",
  "normalized_text_hash": "dedup_hash",
  "issues": [
    {
      "category": "delivery",
      "subcategory": "not_received",
      "evidence": "não recebi o produto",
      "confidence": 0.95
    }
  ],
  "method": "rule",
  "model": null,
  "needs_manual_review": false
}
```

## 9. 最终 JSON 输出

最终输出文件建议为 `extracted_issues.json`，整体结构如下：

```json
{
  "metadata": {
    "source": "olist_order_reviews_dataset.csv",
    "filter": "review_score <= 3",
    "language": "pt-BR",
    "pipeline_version": "q4-v1",
    "record_count": 0
  },
  "records": [
    {
      "review_id": "abc123",
      "order_id": "order456",
      "review_score": 1,
      "raw_text": "Não recebi o produto",
      "issues": [
        {
          "category": "delivery",
          "subcategory": "not_received",
          "evidence": "não recebi o produto",
          "confidence": 0.95
        }
      ],
      "method": "rule",
      "model": null,
      "needs_manual_review": false
    }
  ]
}
```

## 10. 成本控制

该 pipeline 的成本控制来自四个环节：

1. 只处理 `review_score <= 3`。
2. 去重后只对代表文本调用模型。
3. 高频模板和极短评论使用规则引擎。
4. Small LLM 对短评论做 batch 调用，减少请求次数。
5. 只有复杂长评论或低置信度评论才单条调用 Large LLM。

预期覆盖比例：

| 路径 | 预期占比 | 成本影响 |
|---|---:|---|
| Rule Engine | 50%-70% | 无模型成本 |
| Small LLM | 25%-40% | 短评论 batch 调用，降低请求开销 |
| Large LLM | 5%-10% | 单条处理复杂或失败样本 |

实际执行时记录每一步的样本数：

```text
low_score_reviews
-> unique_texts_after_dedup
-> rule_count
-> small_llm_count
-> small_llm_batch_count
-> large_llm_count
-> manual_review_count
```

这样可以在 `cost_report.md` 中解释为什么总成本能控制在 $3 以内，而不是只口头说明“用了小模型”。

## 11. 质量控制

抽样评估建议按处理路径分层抽样，而不是从最终结果里随机抽 30 条：

| 路径 | 抽样目的 |
|---|---|
| Rule Engine 抽 10 条 | 检查模板是否误判，低信息评论是否被强行分类 |
| Small LLM 抽 10 条 | 检查短评论分类准确率和 evidence 是否来自原文 |
| Large LLM 抽 10 条 | 检查多问题抽取、漏召回和复杂语义处理 |

人工标注时重点看三件事：

1. `category/subcategory` 是否正确。
2. `evidence` 是否真实来自原文。
3. 是否漏掉了评论中的主要问题。

如果某类错误频繁出现，应优先修正规则和 prompt，而不是盲目提高模型档位。
