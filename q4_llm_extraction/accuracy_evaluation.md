# Q4 准确率评估方法

Olist 评论没有现成 ground truth，因此不能只看模型输出是否“看起来合理”。本模块采用两层验证：先对全部模型结果做自动质量门禁，再抽 30 条建立人工标注 gold set，用人工结果和模型结果逐项对比。

## 1. 自动校验

所有模型输出必须先通过自动校验，只有通过校验的结果才进入高置信结果池：

1. 输出必须是合法 JSON，并符合预期 schema。
2. `category/subcategory` 必须属于预定义 taxonomy：
   - `delivery`: `delay`, `not_received`, `tracking_issue`
   - `product`: `defective`, `wrong_item`, `poor_quality`, `missing_parts`
   - `service`: `no_response`, `refund_problem`, `seller_attitude`
   - `payment`: `billing_issue`, `refund_delay`
   - `general`: `negative_low_detail`, `unclear`
3. `evidence` 必须能在葡萄牙语原文中找到连续片段，不能是翻译、总结或模型改写。
4. LLM 调用失败、schema 不合法、evidence 无法定位的样本，统一标记为 `needs_manual_review=true`，不作为高置信自动抽取结果。

本次 DeepSeek full live 运行的自动质量门禁结果如下：

| 指标 | 数量 | 处理方式 |
|---|---:|---|
| LLM 调用失败 | 214 | 进入 fallback，标记人工复核 |
| schema 校验失败 | 118 | 不采信模型结构化结果 |
| evidence 校验失败 | 83 | 不采信该 evidence，对应样本人工复核 |

这些数字不是人工准确率，但能提前暴露模型输出中不可直接使用的部分。

## 2. 30 条人工分层抽样

人工评估不直接随机抽 30 条，因为 Rule Engine、Small LLM、Large LLM 的错误类型不同。评估样本从最终输出中按处理路径分层抽样，每层 10 条：

| 分层 | 抽样数 | 检查重点 |
|---|---:|---|
| Rule Engine | 10 | 短评论、模板评论是否被误判，是否过度解释低信息文本 |
| Small LLM | 10 | 短文本主问题分类是否正确，evidence 是否来自原文 |
| Large LLM | 10 | 复杂评论是否漏掉多个问题，是否出现幻觉或 evidence 串错 |

本次运行的路由分布为：Rule `7554`、Small LLM `4836`、Large LLM `1202`，三层样本都足够抽取。抽样时按 `normalized_text_hash` 去重，避免同一句评论重复进入人工评估；如果某层不足 10 条，再从相邻 LLM 层补足，并在评估表中记录来源。

人工标注采用 blind annotation：标注者只看 `raw_text`，不先看模型输出。每条样本手动记录：

1. 主要问题类别，即人工判断的 `category/subcategory`。
2. `severity`，分为 `low`、`medium`、`high`。
3. 原文 `evidence_quote`，必须是葡萄牙语原文中的连续片段。
4. `actionable_for_seller`，判断这个问题是否能被卖家或平台采取行动。
5. 是否存在模型漏抽，即原文有主要问题但模型没有抽出。
6. 是否存在模型幻觉，即模型抽出了原文没有证据支持的问题。

建议人工评估表使用以下字段：

| 字段 | 含义 |
|---|---|
| `sample_id` | 人工评估样本编号 |
| `review_id` | 原评论 ID |
| `route` | `rule` / `small_llm` / `large_llm` |
| `raw_text` | 原始葡萄牙语评论 |
| `human_category` | 人工标注一级类别 |
| `human_subcategory` | 人工标注二级类别 |
| `human_severity` | 人工标注严重程度 |
| `human_evidence_quote` | 人工标注原文证据 |
| `human_actionable_for_seller` | 人工判断是否可行动 |
| `model_category` | 模型输出一级类别 |
| `model_subcategory` | 模型输出二级类别 |
| `model_evidence` | 模型输出 evidence |
| `model_actionable_for_seller` | 模型或评估规则得到的可行动判断 |
| `missed_main_issue` | 是否漏掉主要问题 |
| `hallucinated_issue` | 是否存在无原文证据的问题 |

当前抽取结果没有单独保存 `severity` 和 `actionable_for_seller` 字段，因此人工表仍记录这两项；`actionable_for_seller` 的模型侧判断先用固定规则补齐：`delivery`、`product`、`service`、`payment` 视为 `true`，`general.negative_low_detail`、`general.unclear` 或 `needs_manual_review=true` 视为 `false`。如果后续 schema 直接输出 `actionable_for_seller`，则以模型字段为准。

## 3. 对比指标

对比时以 30 条人工 gold set 为准，计算以下指标：

- 分类准确率 = 一级 `category` 判断正确的样本数 / 30。
- evidence 合规率 = evidence 来自原文且能支持分类的模型 issue 数 / 模型抽取 issue 数。
- 漏召回率 = 人工标注中存在但模型漏掉的主要问题数 / 人工标注主要问题数。
- 幻觉率 = 模型抽取但原文没有证据支持的 issue 数 / 模型抽取 issue 数。
- actionable 判断准确率 = `actionable_for_seller` 判断正确样本数 / 30。

分类准确率按“主要问题是否命中”计算；如果一条评论有多个问题，模型至少需要抽中人工标注的主问题才算该样本分类正确。evidence 合规率和幻觉率按 issue 级别计算，因为一条评论可能有多个模型 issue。

## 4. 错误反馈

评估结果用于迭代 pipeline，而不是只报告一个准确率：

- 如果 Rule Engine 误判集中出现，优先修正规则关键词和低信息评论处理逻辑。
- 如果 Small LLM 错误集中在短文本分类，优先改 batch prompt 和分类示例。
- 如果 Large LLM 出现漏召回，优先检查复杂评论是否被截断、是否限制了 issue 数量。
- 如果 evidence 不合规或幻觉率高，优先收紧 prompt、schema 校验和 evidence substring 校验，而不是直接升级模型。

这样即使没有官方 ground truth，也可以用小规模人工 gold set 验证抽取是否可靠，并把错误样本反馈回规则、prompt 和校验逻辑。

## 5. 本次 30 条抽样评估结果

本次从 `extracted_issues_live_sample.json` 中按处理方式各抽 10 条非空文本样本，抽样规则为：先筛选 `method in (rule, small_llm, large_llm)`，再按 `review_id + raw_text` 的稳定 hash 排序取前 10 条。人工标注时只看 `raw_text`，再和模型输出对比。

本次指标按以下口径计算：

- 分类准确率只看一级 `category` 是否正确。
- evidence 合规率、幻觉率按模型输出的 issue 数计算。
- 漏召回率按人工标注出的主要 issue 数计算；对于 `Chegou bem`、`bom tinha cancelado...chegar antes do prazo` 这类没有可抽取问题的样本，不进入漏召回分母。
- `actionable_for_seller` 当前由模型类别补齐：`delivery/product/service/payment=true`，`general` 或 `needs_manual_review=true=false`。

### 5.1 总体指标

| 指标 | 计算 | 结果 |
|---|---:|---:|
| 分类准确率 | 25 / 30 | 83.3% |
| evidence 合规率 | 28 / 34 | 82.4% |
| 漏召回率 | 6 / 35 | 17.1% |
| 幻觉率 | 3 / 34 | 8.8% |
| actionable 判断准确率 | 28 / 30 | 93.3% |

### 5.2 分层结果

| 分层 | 分类正确 | evidence 合规 | 漏召回 | 幻觉 | actionable 正确 |
|---|---:|---:|---:|---:|---:|
| Rule Engine | 7 / 10 | 7 / 10 | 4 / 10 | 3 / 10 | 9 / 10 |
| Small LLM | 9 / 10 | 10 / 11 | 2 / 12 | 0 / 11 | 9 / 10 |
| Large LLM | 9 / 10 | 11 / 13 | 0 / 13 | 0 / 13 | 10 / 10 |

### 5.3 样本级判断摘要

| 样本 | 人工主类 | 模型主类 | 分类正确 | 漏抽数 | 幻觉数 | 说明 |
|---|---|---|---:|---:|---:|---|
| rule-1 | delivery + service | delivery | 1 | 1 | 0 | 未收到货正确，但漏掉卖家不回复 |
| rule-2 | delivery | delivery | 1 | 0 | 0 | 超过期限未送达，分类正确 |
| rule-3 | general | general | 1 | 0 | 1 | 原文是“Chegou bem”，负面低信息判断不成立 |
| rule-4 | delivery | delivery | 1 | 0 | 0 | 未送达/延迟，一级分类正确 |
| rule-5 | product | delivery | 0 | 1 | 1 | 商品面板印刷弱、与图片不同，被误判成物流延迟 |
| rule-6 | delivery + service | delivery | 1 | 1 | 0 | 未收到货正确，但漏掉联系店铺无回复 |
| rule-7 | delivery | delivery | 1 | 0 | 0 | 配送太慢，分类正确 |
| rule-8 | product | delivery | 0 | 1 | 0 | 未收到完整订单，更接近缺件 |
| rule-9 | general | delivery | 0 | 0 | 1 | 原文说提前到货后保留商品，延迟判断不成立 |
| rule-10 | delivery | delivery | 1 | 0 | 0 | 未收到货，分类正确 |
| small-1 | product | product | 1 | 0 | 0 | 收到旧产品，商品问题 |
| small-2 | delivery | delivery | 1 | 0 | 0 | 长时间未到货 |
| small-3 | product | product | 1 | 0 | 0 | 收到平行/非预期商品 |
| small-4 | product | product | 1 | 0 | 0 | 商品质量弱 |
| small-5 | delivery + service | delivery + service | 1 | 0 | 0 | 未送达且无回复，两个 issue 都抽到 |
| small-6 | payment | general | 0 | 1 | 0 | 发票/抬头更正问题被归为 unclear |
| small-7 | product | product | 1 | 0 | 0 | 1L 洗发水收到 300ml |
| small-8 | payment + delivery | payment | 1 | 1 | 0 | 订单日期问题抽到，但漏掉等待送达 |
| small-9 | delivery | delivery | 1 | 0 | 0 | 缺货未收到，可按未收到处理 |
| small-10 | delivery | delivery | 1 | 0 | 0 | 未送达，分类正确 |
| large-1 | product | product | 1 | 0 | 0 | 缺少 3G modem/配件 |
| large-2 | product | product | 1 | 0 | 0 | 商品过期 |
| large-3 | product | product | 1 | 0 | 0 | 音质和电池质量差 |
| large-4 | delivery | delivery | 1 | 0 | 0 | 先发票后商品造成物流状态困惑 |
| large-5 | delivery + service | delivery + service | 1 | 0 | 0 | 无库存未收到且未退款 |
| large-6 | product | product | 1 | 0 | 0 | 尺寸/描述不一致；第二个 issue 子类不够准 |
| large-7 | service | product | 0 | 0 | 0 | 更像合作商未履约，不是商品质量 |
| large-8 | delivery + service | delivery + service | 1 | 0 | 0 | 等待送达且发消息无回复 |
| large-9 | delivery | delivery | 1 | 0 | 0 | 仍在等待商品 |
| large-10 | product | product | 1 | 0 | 0 | 零件尺寸/装配问题 |

### 5.4 结论

这 30 条样本里，Small LLM 和 Large LLM 的分类表现明显好于 Rule Engine。Rule Engine 的主要问题是关键词过宽：例如出现“antes do prazo”仍可能被规则误判成 `delivery.delay`，以及 `Chegou bem` 这种低分但正向评论被误判为负面低信息。下一步优先修正规则层的否定/反向语义和正向短句识别，其次再优化 Large LLM 对“商家未履约”和“描述信息缺失”这类边界问题的分类。
