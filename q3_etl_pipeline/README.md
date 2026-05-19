# Q3 - 端到端 ETL Pipeline

请在本目录下完成模块 3 的 ETL Pipeline。完整题目描述见根目录的 `README.md`。

## 📦 期望产出

```
q3_etl_pipeline/
├── README.md                    # 本文件
├── pipeline.py                  # 主程序
├── outputs/
│   ├── sales_facts.parquet      # 输出 1：真实销售（BI 报表用）
│   ├── customer_features.parquet # 输出 2：客户 RFM 特征
│   └── returns_log.parquet      # 输出 3：退货记录（含原单匹配）
├── pipeline_log.txt             # 完整运行日志
└── validation_report.md         # 数据校验报告
```

## 💡 关键提示

### 退货匹配（Q3.1 最难的部分）

一个退货 invoice `C536379` 含 `quantity=-5`，需要找它对应的原始购买记录：
- 同一客户
- 同一商品
- `quantity=5`（即 |退货数量|）
- 时间早于退货日期
- 离退货时间最近

**你需要思考**：
- 如果多笔正向销售符合条件，匹配哪一笔？
- 如果客户买了 10 个、分两次退货各退 5 个怎么办？
- 如果原单的 quantity 比退货的小怎么办？

这些**业务规则**需要候选人自己思考，请在 `REFLECTION.md` 中详细说明你的设计。

### 性能要求

- **禁止使用** `iterrows()` / `apply` 循环全表（除非有充分理由）
- 100 万行应在 **2 分钟内** 跑完
- 推荐使用 `pandas` 矢量化 + `merge_asof` 做时间匹配

## 🎯 评分关注点

| 项目 | 分值 |
|------|------|
| 输出 1 销售口径准确性 | 4 分 |
| 输出 2 RFM 计算正确性 | 4 分 |
| 输出 3 退货匹配（**最难**） | 5 分 |
| 代码工程化（模块化/日志/异常） | 4 分 |
| 性能与可重现性 | 3 分 |
