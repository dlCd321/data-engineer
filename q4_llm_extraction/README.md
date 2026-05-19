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
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

**绝对不要把 API Key 提交到 Git！**

## 🎯 评分关注点

| 项目 | 分值 |
|------|------|
| 分流策略合理性 | 4 分 |
| Prompt 设计质量 | 4 分 |
| 成本控制 | 3 分 |
| 准确率评估方法 | 4 分 |
