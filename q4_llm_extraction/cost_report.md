# Q4 成本报告

## 1. 默认运行模式

`python run_all.py` 调用 Q4 时默认使用 `offline` 模式，因此不会因为缺少 API key 失败，也不会产生模型费用。offline 输出主要用于保证一键运行可复现；其中 Small/Large LLM 路由样本会被标记为 `general.unclear` 和 `needs_manual_review=true`。

| 指标 | offline 默认输出 |
|---|---:|
| live LLM 是否调用 | 否 |
| 估算成本 | 0 |
| 实际模型账单 | 0 |
| LLM 调用次数 | 0 |
| LLM 失败次数 | 0 |

## 2. full live 验证结果

为了验证真实模型路径，本次另行使用 DeepSeek provider 跑了一次 full live。该运行处理全部去重文本，不是默认提交入口；运行时关闭本地成本上限，因此可以观察完整链路的真实耗时、失败率和账单。

| 指标 | 数值 |
|---|---:|
| Provider | DeepSeek |
| Small model | `deepseek-v4-flash` |
| Large model | `deepseek-v4-pro` |
| 低分评论数 | 22,754 |
| 空文本低分评论数 | 8,117 |
| 去重后文本数 | 13,592 |
| live_sample_requested | 0 |
| live_sample_actual | 13,592 |
| 实际耗时 | 47 分钟 |
| 实际账单成本 | 14 RMB |
| 脚本保守估算成本 | $10.999849 |
| 估算输入 tokens | 950,591 |
| 估算输出 tokens | 1,522,250 |
| 服务端返回输入 tokens | 612,111 |
| 服务端返回输出 tokens | 2,262,273 |
| 服务端返回总 tokens | 2,874,384 |
| LLM 调用次数 | 2,259 |
| LLM 失败次数 | 214 |
| schema 校验失败 | 118 |
| evidence 校验失败 | 83 |
| budget_exhausted | false |

脚本中的 `$10.999849` 是调用前按本地 token 估算和保守单价得到的上限估计，不等同于实际账单。实际账单以 DeepSeek 后台为准，本次为 14 RMB。成本低于题目给出的 $3 预算，但 47 分钟超过 40 分钟约束 7 分钟。

## 3. 分流规模

| 路由 | 去重文本数 | 占去重文本比例 |
|---|---:|---:|
| Rule Engine | 7,554 | 55.6% |
| Small LLM | 4,836 | 35.6% |
| Large LLM | 1,202 | 8.8% |
| 合计 | 13,592 | 100.0% |

实际处理方式和初始路由不完全相同，因为部分 Small LLM 样本会因 schema、evidence 或低置信度进入 Large LLM retry，部分失败样本会进入 offline fallback。

| method | 数量 | 说明 |
|---|---:|---|
| `rule` | 7,554 | 规则直接处理 |
| `small_llm` | 1,484 | Small LLM 成功返回 |
| `large_llm` | 2,041 | Large LLM 成功返回，包含部分升级样本 |
| `offline_small_llm_fallback` | 2,461 | Small LLM 路径失败或未调用后的 fallback |
| `offline_large_llm_fallback` | 52 | Large LLM 路径失败后的 fallback |

## 4. 单条成本口径

按本次实际账单 14 RMB 计算：

| 分母 | 平均成本 |
|---|---:|
| 22,754 条低分评论 | 约 0.00062 RMB / 条 |
| 13,592 条去重文本 | 约 0.00103 RMB / 条 |
| 2,259 次 LLM 调用 | 约 0.00620 RMB / 次 |

这个平均成本很低，主要来自三点：先过滤 `review_score <= 3`，再对 `normalized_text` 去重，最后用 Rule Engine 处理 55.6% 的去重文本。真正的工程风险不是账单，而是耗时和失败处理：Large LLM 单条调用、214 次 LLM 失败、118 次 schema 错误和 83 次 evidence 错误会拉长运行时间。

## 5. 成本控制结论

本次 full live 说明，DeepSeek 分流方案可以把实际账单控制在 $3 预算内，但还没有稳定满足 40 分钟时限。若要严格卡 40 分钟，应保留默认 `--max-cost-usd 3.0`，并进一步减少 Large LLM 覆盖面：低价值低置信样本直接进入人工复核队列，只有包含退款、错发、损坏、缺件、客服无响应等高价值业务信号的样本才升级到 Large LLM。
