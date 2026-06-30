# Q4 成本报告

## 执行模式

- 模式：`offline`
- live LLM 是否调用：`否`
- Provider：`none`
- Small model：`none`
- Large model：`none`
- 成本上限：`$3.00`
- 估算成本：`$0.000000`
- 估算输入/输出 tokens：`0` / `0`
- 服务端返回输入/输出 tokens：`0` / `0`
- LLM 调用次数：`0`
- LLM 失败次数：`0`
- budget_exhausted：`False`

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
| live_sample_actual | 0 |
| Rule Engine 实际处理 | 7554 |
| Small LLM 实际处理 | 4836 |
| Large LLM 实际处理 | 1202 |

## 实际处理方式

| method | 数量 |
|---|---:|
| `offline_large_llm_fallback` | 1220 |
| `offline_small_llm_fallback` | 4935 |
| `rule` | 16599 |

## 成本控制说明

1. 只处理 `review_score <= 3` 的评论。
2. 对 `normalized_text` 做精确去重，模型只需要处理代表文本。
3. 空评论、极短评论和高置信度模板由本地规则处理。
4. 短文本才进入 Small LLM batch；复杂长文本或低置信度结果才升级到 Large LLM。
5. live 模式下每次调用前都会做 token 估算；如果设置了成本上限，预计成本超过上限会停止；如果传入 `--no-cost-limit`，则不做本地预算 gate。

本次 offline 输出中，Small/Large LLM 路由样本被标记为 `general.unclear` 和 `needs_manual_review=true`，用于保证一键运行可复现、零成本。
