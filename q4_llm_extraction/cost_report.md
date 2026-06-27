# Q4 成本报告

## 执行模式

- 模式：`live`
- live LLM 是否调用：`是`
- Provider：`deepseek`
- Small model：`deepseek-v4-flash`
- Large model：`deepseek-v4-pro`
- 成本上限：`不设限`
- 实际账单成本：`14 RMB`
- 实际端到端耗时：`47 分钟`
- 脚本估算成本：`$10.999849`
- 估算输入/输出 tokens：`950591` / `1522250`
- 服务端返回输入/输出 tokens：`612111` / `2262273`
- LLM 调用次数：`2259`
- LLM 失败次数：`214`
- schema_error_count：`118`
- evidence_error_count：`83`
- budget_exhausted：`False`

本次 full live 运行使用 DeepSeek provider，`live_sample_requested=0` 表示不抽样而是处理全部去重文本；同时传入了 `--no-cost-limit`，因此本地预算 gate 没有拦截模型调用。脚本中的 `$10.999849` 是按内置 token 单价做的保守估算，DeepSeek 平台实际扣费以账单为准，本次真实成本为 14 RMB。

默认运行使用 offline 模式，因此 `python run_all.py` 或 `uv run python run_all.py` 不会因为缺少 API key 失败，也不会产生模型费用。需要真实调用模型时，必须显式传入 `--mode live` 并配置 `OPENROUTER_API_KEY` 或 `DEEPSEEK_API_KEY`。live 模式默认只抽样验证 DeepSeek/OpenRouter 模型路径，不直接全量调用所有 LLM 路由。

## 样本量与分流

| 指标 | 数量 |
|---|---:|
| 低分评论数 | 22754 |
| 空文本低分评论数 | 8117 |
| 去重后文本数 | 13592 |
| Rule Engine 路由 | 7554 |
| Small LLM 路由 | 4836 |
| Large LLM 路由 | 1202 |

## 本次实际处理路由

| 指标 | 数量 |
|---|---:|
| live_sample_requested | 0 |
| live_sample_actual | 13592 |
| Rule Engine 实际处理 | 7554 |
| Small LLM 实际处理 | 4836 |
| Large LLM 实际处理 | 1202 |

## 实际成本拆分

| 指标 | 数值 |
|---|---:|
| 实际账单成本 | 14 RMB |
| 实际端到端耗时 | 47 分钟 |
| 每条低分评论平均成本 | 0.0006 RMB |
| 每条去重文本平均成本 | 0.0010 RMB |
| 每次 LLM 调用平均成本 | 0.0062 RMB |
| 每分钟处理去重文本 | 约 289 条 |
| 每分钟回写原始评论 | 约 484 条 |

从实际账单看，DeepSeek 的 full live 成本仍在 $3 预算的大致量级内；但 47 分钟超过了题目给出的 40 分钟时限。主要原因是这次为了得到完整 live 结果没有启用本地预算 gate，并且 214 次 LLM 调用失败、118 次 schema 校验失败、83 次 evidence 校验失败会带来额外等待和 fallback 处理。若按正式生产配置执行，应保留 `--max-cost-usd 3.0`，并根据 40 分钟 SLA 进一步调高并发或只对高价值复杂评论做 live。

## 实际处理方式

| method | 数量 |
|---|---:|
| `large_llm` | 2041 |
| `offline_large_llm_fallback` | 52 |
| `offline_small_llm_fallback` | 2461 |
| `rule` | 7554 |
| `small_llm` | 1484 |

## 成本控制说明

1. 只处理 `review_score <= 3` 的评论。
2. 对 `normalized_text` 做精确去重，模型只需要处理代表文本。
3. 空评论、极短评论和高置信度模板由本地规则处理。
4. 短文本才进入 Small LLM batch；复杂长文本或低置信度结果才升级到 Large LLM。
5. live 模式下每次调用前都会做 token 估算；如果设置了成本上限，预计成本超过上限会停止；如果传入 `--no-cost-limit`，则不做本地预算 gate。

本次提交同时保留 offline 默认路径和 DeepSeek full live 运行记录：offline 输出保证一键运行可复现、零成本；full live 输出用于证明真实模型链路、成本和耗时。Small/Large LLM 失败或校验不通过的样本会输出 fallback，并设置 `needs_manual_review=true`，避免把不可靠抽取当成确定结论。
