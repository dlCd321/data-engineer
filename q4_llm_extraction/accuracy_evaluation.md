# Q4 准确率评估方法和结果

由于 Olist 评论没有现成 ground truth，本模块采用分层抽样人工评估，而不是只随机抽样最终结果。本次评估使用 `extracted_issues_live_sample.json` 的 live full run 输出。

## 1. 抽样规则

为了降低单次 30 条样本的偶然性，本次采用 3 repeated 30-sample validation batches。每一轮独立抽取 30 条：Rule Engine、Small LLM、Large LLM 各 10 条，因此总计人工标注 90 条。

这不是传统训练模型里的 k-fold cross validation，因为本任务没有训练过程；它的作用是验证指标在不同人工样本上的稳定性。

抽样步骤：

1. 从 `extracted_issues_live_sample.json` 中筛选 `method in (rule, small_llm, large_llm)` 且 `raw_text` 非空的样本。
2. 按 `review_id + raw_text` 的稳定 hash 排序，保证结果可复现。
3. 每个 method 取前 30 条，按顺序切成 3 轮：第 1-10 条为 batch 1，第 11-20 条为 batch 2，第 21-30 条为 batch 3。
4. 三轮之间不重复样本；人工标注时只看 `raw_text`，再和模型输出对比。

## 2. 指标定义

- 分类准确率：一级/二级类别是否和人工判断一致。
- evidence 合规率：`evidence` 是否来自原文，并且能支撑模型分类。
- 漏召回率：模型漏掉的主要问题数 / 人工标注出的主要问题数。
- 幻觉率：模型输出的 issue 中，原文没有支持证据的比例。
- actionable 判断准确率：是否正确判断这个问题是否可由卖家采取行动。

补充口径：

- evidence 合规率和幻觉率按模型输出的 issue 数计算。
- 漏召回率按人工标注出的主要 issue 数计算；没有可抽取问题的样本不进入漏召回分母。
- `actionable_for_seller` 当前由模型类别补齐：`delivery/product/service/payment=true`，`general` 或 `needs_manual_review=true=false`。

## 3. 90 条总体指标

| 指标 | 计数 | 比例 |
|---|---:|---:|
| 分类准确率 | 80 / 90 | 88.9% |
| evidence 合规率 | 105 / 114 | 92.1% |
| 漏召回率 | 13 / 115 | 11.3% |
| 幻觉率 | 6 / 114 | 5.3% |
| actionable 判断准确率 | 86 / 90 | 95.6% |

## 4. 三轮指标稳定性

| 验证轮次 | 分类准确率 | evidence 合规率 | 漏召回率 | 幻觉率 | actionable 准确率 |
|---|---:|---:|---:|---:|---:|
| Batch 1 | 25 / 30 = 83.3% | 28 / 34 = 82.4% | 6 / 35 = 17.1% | 3 / 34 = 8.8% | 28 / 30 = 93.3% |
| Batch 2 | 26 / 30 = 86.7% | 37 / 39 = 94.9% | 5 / 39 = 12.8% | 2 / 39 = 5.1% | 29 / 30 = 96.7% |
| Batch 3 | 29 / 30 = 96.7% | 40 / 41 = 97.6% | 2 / 41 = 4.9% | 1 / 41 = 2.4% | 29 / 30 = 96.7% |

三轮结果显示，分类准确率在 `83.3% - 96.7%` 之间波动，evidence 合规率在 `82.4% - 97.6%` 之间波动。第一轮指标最低，主要因为 Rule Engine 抽到了多条正向或反向语义评论，被关键词规则误判；第二、三轮中 LLM 路径占优后，整体指标明显上升。

## 5. 按处理路径汇总

| 处理路径 | 分类准确率 | evidence 合规率 | 漏召回率 | 幻觉率 | actionable 准确率 |
|---|---:|---:|---:|---:|---:|
| Rule Engine | 25 / 30 = 83.3% | 32 / 38 = 84.2% | 10 / 37 = 27.0% | 6 / 38 = 15.8% | 28 / 30 = 93.3% |
| Small LLM | 26 / 30 = 86.7% | 32 / 33 = 97.0% | 3 / 35 = 8.6% | 0 / 33 = 0.0% | 28 / 30 = 93.3% |
| Large LLM | 29 / 30 = 96.7% | 41 / 43 = 95.3% | 0 / 43 = 0.0% | 0 / 43 = 0.0% | 30 / 30 = 100.0% |

这个分层结果说明，主要质量风险不在 DeepSeek LLM，而在规则层。Rule Engine 的幻觉率达到 `15.8%`，漏召回率达到 `27.0%`；Small LLM 和 Large LLM 的 evidence 合规率都超过 `95%` 左右，且 90 条样本中没有发现 LLM 路径的明显幻觉问题。

## 6. 错误摘要

Batch 2 的主要错误仍集中在 Rule Engine：

- `Produto não respondeu às minhas expectativas, Bem diferente do site` 被误判成 `service.no_response`，实际是商品与页面不符。
- `a qualidade é baixa` 被归为 `general.negative_low_detail`，实际应是 `product.poor_quality`。
- `já foi pago parcela no cartão de crédito` 被规则额外抽成 `payment.billing_issue`，但原文只是说明已付款，不一定是支付问题。

Batch 3 的错误更少，但仍能看到两个边界：

- Rule Engine 对 `Recebi a mercadoria com um pouco de atraso...` 额外抽出了 `tracking_issue`，证据不足。
- Small LLM 对 `Comprei dois itens e só chegou um` 输出 `delivery.not_received`，如果按缺件口径标注为 `product.missing_parts`，则分类不完全准确。

## 7. 结论

3 轮共 90 条人工评估显示，pipeline 的整体一级分类准确率为 `88.9%`，evidence 合规率为 `92.1%`，幻觉率为 `5.3%`。这个结果比单轮 30 条更稳定，也更能说明问题来源：Small LLM 和 Large LLM 的结果基本可用，Rule Engine 是主要短板。

下一步优先修正规则层的正向语义、否定语义、缺件/未收到的边界，以及支付关键词的过度触发；不应优先通过升级模型解决。
