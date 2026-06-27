# Q4 - LLM 抽取（评价文本结构化）

请在本目录下完成模块 4。完整题目描述见根目录的 `README.md`。

## 📦 期望产出

```
q4_llm_extraction/
├── README.md                # 本文件
├── extract_reviews.py       # 主程序
├── prompt_template.txt      # Prompt 模板
├── extracted_issues.json    # 抽取结果
├── pipeline_design.md       # 设计文档（300-500 字）
├── cost_report.md           # 成本报告
└── accuracy_evaluation.md   # 准确率评估方法和结果
```

## ⚠️ 重要约束

- **成本预算**：$3 USD 总成本上限（**会查实际账单**）
- **时长**：40 分钟
- **不允许全部用 GPT-4 处理所有评论**（成本会爆，且没必要）

## ✅ 本次实现摘要

- 默认可复现路径：`offline`，不依赖 API key，不产生模型费用。
- 真实模型验证路径：`live` + `provider=deepseek`。
- 使用模型：Small LLM 为 `deepseek-v4-flash`，Large LLM 为 `deepseek-v4-pro`。
- full live 实际耗时：47 分钟。
- full live 实际账单成本：14 RMB。
- 处理规模：22,754 条低分评论，去重后 13,592 条文本。
- 分流结果：Rule Engine 7,554 条，Small LLM 4,836 条，Large LLM 1,202 条。

本次 full live 为了验证完整链路关闭了本地成本上限，因此耗时超过 40 分钟约束 7 分钟。正式生产运行时建议保留 `--max-cost-usd 3.0`，并把低价值失败样本直接进入人工复核队列，避免为了追求全自动覆盖而拖慢整体 SLA。

## 💡 关键决策点

1. **分流策略**：哪些评论值得用大模型处理？哪些用规则/小模型？
   - 提示：很多"差评"其实只有 "ruim"（差）一个词，根本不需要 LLM
   
2. **Prompt 设计**：
   - 怎么让 LLM 输出严格的 JSON
   - 葡萄牙语怎么处理？让 LLM 翻译还是用专门翻译模型？
   - 怎么避免幻觉（LLM 编造原文没有的问题）？

3. **批处理**：单条请求 vs 批量请求的成本对比

4. **评估准确率**：
   - 你没有 ground truth
   - 抽样 30 条人工标注 → 对比？这个流程你怎么设计？

## 🔧 API Key 配置

请在仓库根目录创建 `.env` 文件（已加入 .gitignore）：

```
OPENROUTER_API_KEY=sk-or-...
DEEPSEEK_API_KEY=sk-...
```

**绝对不要把 API Key 提交到 Git！**

本次提交的真实运行使用 DeepSeek direct provider。建议先抽样跑通：

```bash
uv run python q4_llm_extraction/extract_reviews.py \
  --mode live \
  --provider deepseek \
  --live-sample-size 30 \
  --max-cost-usd 0.50
```

如果确认要不抽样、不设本地预算上限跑完整 live pipeline：

```bash
uv run python q4_llm_extraction/extract_reviews.py \
  --mode live \
  --provider deepseek \
  --live-sample-size 0 \
  --no-cost-limit
```

这会真实调用所有进入 Small/Large LLM 路由的去重评论，可能产生明显 API 费用。

## 🎯 评分关注点

| 项目 | 分值 |
|------|------|
| 分流策略合理性 | 4 分 |
| Prompt 设计质量 | 4 分 |
| 成本控制 | 3 分 |
| 准确率评估方法 | 4 分 |
