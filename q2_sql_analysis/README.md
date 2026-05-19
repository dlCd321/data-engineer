# Q2 - SQL 与业务分析

请在本目录下完成模块 2 的所有 SQL 题目。完整题目描述见根目录的 `README.md`。

## 📦 期望产出

```
q2_sql_analysis/
├── README.md                       # 本文件
├── load_olist.py                   # （可选）把 9 张 CSV 灌进 MySQL 的脚本
├── q2_1_translation_gap.sql        # 商品类别翻译完整性
├── q2_2_monthly_metrics.sql        # 平台真实成交分析
├── q2_3_top_sellers.sql            # 卖家维度分析
└── q2_4_query_optimization.md      # 慢查询优化（分析文档）
```

## 💡 强制要求：MySQL 8.0+

本模块**必须使用 MySQL 8.0+**（团队生产数据库），不允许用 SQLite 等代替。


## 🎯 评分关注点

| 题 | 关注什么 |
|----|----------|
| Q2.1 | 是否找出 3 个未翻译的类别 |
| Q2.2 | GMV 口径是否含 freight_value、NULL 送达时间是否正确处理 |
| Q2.3 | 窗口函数使用、reviews 表去重、SQL 可读性 |
| Q2.4 | 是否识别了 JOIN 后 SUM 翻倍的统计错误（**重点**）；MySQL 索引设计是否合理 |
