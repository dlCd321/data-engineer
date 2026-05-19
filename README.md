# 数据工程师笔试题

> **总时长**：4 小时 | **总分**：100 分 + 加分题 15 分
> 
> **数据集**：
> - 📦 **Online Retail II**（UCI / Kaggle）：~1.06M 行真实英国电商交易，2009-12 至 2011-12，38+ 国家
> - 🇧🇷 **Brazilian E-Commerce by Olist**（Kaggle）：100k 订单，9 张关联表，含评价文本

---

## 📋 考试说明（请务必先读）

### 📦 笔试材料地址

GitHub：`https://github.com/Jay-gekko/written-test`（请 Fork 到自己的 GitHub 仓库）

仓库内容：
- `README.md` - 本笔试题目
- `run_all.py` - 一键运行入口（候选人需在此接入各模块）
- `REFLECTION.md` / `TOOLS.md` / `AI_LOG.md` - 待填充的反思文档模板（必填）
- `q1_data_quality/` ~ `q5_system_design/` / `bonus/` - 各模块代码与文档骨架
- `data/` - 数据集存放目录（CSV 文件需自行下载，详见下方"📦 数据准备"）

---

### 📦 数据准备

笔试用到的两份数据集**不随仓库分发**，请自行下载到本地 `data/` 目录：

| 数据集 | Kaggle 链接 | 用于模块 |
|--------|-------------|----------|
| Online Retail II（UCI） | https://www.kaggle.com/datasets/mashlyn/online-retail-ii-uci | 模块 1（Q1）、模块 3（Q3） |
| Brazilian E-Commerce by Olist | https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce | 模块 2（Q2）、模块 4（Q4） |

**要求**：

- 请自行编写下载脚本（推荐放在 `run_all.py` 或单独的 `download_data.py` 里），使 `python run_all.py` 能从 0 到 1 跑通**包含数据下载**的完整 pipeline
- 推荐使用 `kagglehub` / Kaggle CLI；也可手动下载后解压到 `data/`
- 期望最终目录结构（题目代码中引用的路径）：

  ```
  data/
  ├── online_retail_ii.csv                       # Online Retail II
  └── olist/
      ├── olist_customers_dataset.csv
      ├── olist_geolocation_dataset.csv
      ├── olist_order_items_dataset.csv
      ├── olist_order_payments_dataset.csv
      ├── olist_order_reviews_dataset.csv
      ├── olist_orders_dataset.csv
      ├── olist_products_dataset.csv
      ├── olist_sellers_dataset.csv
      └── product_category_name_translation.csv
  ```

> 💡 Kaggle 原始下载文件名可能是 `online_retail_II.csv`（大写 II），请在下载脚本里**统一重命名**为题目代码使用的 `online_retail_ii.csv`，避免大小写敏感的文件系统上路径不一致。

#### ⚠️ 严禁把数据集 CSV 提交到 Fork 仓库

- 单个 CSV 体积大（Online Retail II ~45MB、Olist 多个文件合计 ~120MB），GitHub 单文件上限 100MB 会**直接拒绝 push**
- 仓库膨胀会让我们 review 你的 diff 变困难
- 本仓库 `.gitignore` 已配置忽略规则：
  ```
  data/*.csv
  data/*.xlsx
  data/*.parquet
  data/olist/
  data/Online Retail II*/
  data/Brazilian E-Commerce*/
  !data/.gitkeep
  ```
- **请勿修改 `.gitignore` 来强行把 CSV 提交进仓库**——这会被视为不规范操作，在评分时体现
- 同样地：**Q3 的 `outputs/*.parquet`、`pipeline_log.txt` 也不要提交**（`.gitignore` 已忽略）；我们会通过 `python run_all.py` 自行复现你的产物

---

### 🛠️ 允许与鼓励使用的工具

- **鼓励使用** AI 工具（ChatGPT、Claude、Copilot、Cursor 等）
- **鼓励使用** 任何搜索引擎、开源代码、Stack Overflow、官方文档
- **可使用** 任何 IDE、数据库客户端（DBeaver、DataGrip、Jupyter、MySQL Workbench 等）
- **数据库统一使用 MySQL 8.0+**（团队生产数据库，不允许用 SQLite 代替）
- **必须如实记录** 所有使用的工具与方法

> ⚠️ 我们不限制工具，但**我们会在面试中就你的代码进行追问**。如果你无法解释自己代码的核心实现，会被视为提交无效。

---

### 关于使用 AI 工具

**允许并鼓励使用 AI**（Claude、ChatGPT、Copilot 等）。但请注意，本试卷的**所有题目都是针对真实数据集设计的**——AI 看不到数据，无法直接给出答案。

我们考察的不是「你能不能写代码」，而是：
- 你能否**正确分解问题**给 AI
- 你能否**验证 AI 输出**的正确性  
- 你能否**发现 AI 答案的盲区**
- 你能否做出**只有看了数据才能做的判断**

直接复制 AI 答案的人会在本试卷拿低分（因为 AI 的"通用清洗方案"会漏掉这两份数据集特有的问题）。


---

### 📤 提交方式与规范

#### 1. 代码提交要求

- **Fork** 项目到自己的 GitHub 仓库（**不要**新建空仓库或私有仓库）
- **代码注释和文档请使用中文撰写**（团队内部沟通语言）
- 提供完整的可运行代码
- **环境要求**：
  - Python 3.10+
  - 提供 `requirements.txt` 锁定所有依赖
  - 确保 `python run_all.py` 能从 0 到 1 跑通整个 pipeline（含数据下载）
  - 每个模块也可独立运行（不要因为模块 1 报错导致后面全跑不了）

#### 2. 文档提交（三份必填）

**📝 `REFLECTION.md`** - 反思文档，每道题需补充：
- **实现思路**：不只是代码做了什么，而是为什么这么做
- **遇到的坑和踩雷**：具体说明，不要写"碰到一些问题"这种废话
- **性能优化**（如果有）：列出优化前后的对比数据
- **未完成的部分**：明确说明哪些没做完、卡在哪里（不扣分）
- **你认为本试卷哪道题设计不合理或有歧义**（这是**加分项**不是减分项）
- **如果再做一次，你会怎么改进自己的代码**

**🛠️ `TOOLS.md`** - 工具与软件使用清单，每个工具需说明：
- **解决了什么问题**
- **使用场景或关键步骤**
- **如果不用这个工具，替代方案是什么**

示例：
```markdown
## MySQL 8.0
- 解决了什么问题：完成 Q2 所有 SQL 查询（本试卷强制使用，对齐团队生产数据库）
- 使用场景：用 pandas.to_sql + SQLAlchemy 把 Olist 9 张 CSV 灌进 olist 库，通过 DBeaver/MySQL Workbench 执行 .sql 文件
- 替代方案：无（强制要求）。本地起 MySQL 嫌麻烦的话可用 Docker：`docker run -d --name mysql -e MYSQL_ROOT_PASSWORD=xxx -p 3306:3306 mysql:8`
```

**🤖 `AI_LOG.md`** - AI 完整对话记录
- 提供与 AI 的**完整对话记录**（**原文，不要删改、不要总结**）
- 每段对话需标注：**对应哪道题、第几次迭代**
- 形式可以是导出文件、截图或文本

#### 3. 提交方式

1. 将你的 GitHub 仓库**设为公开**
2. 通过邮件回复**可访问的 Git 仓库地址**
3. 附上最终提交的 `commit hash`（防止提交后继续修改造成纠纷）

#### 4. 仓库结构

```
your_fork/
├── README.md                  # 候选人简介、整体说明
├── REFLECTION.md              # 反思文档（必填）
├── TOOLS.md                   # 工具清单（必填）
├── AI_LOG.md                  # AI 完整对话记录（必填）
├── requirements.txt           # 依赖锁定
├── run_all.py                 # 一键运行入口
│
├── q1_data_quality/
│   ├── data_quality_report.md
│   ├── findings.md
│   ├── cleaning_strategy.md
│   └── q1_code.py
│
├── q2_sql_analysis/
│   ├── q2_1_translation_gap.sql
│   ├── q2_2_monthly_metrics.sql
│   ├── q2_3_top_sellers.sql
│   └── q2_4_query_optimization.md
│
├── q3_etl_pipeline/
│   ├── pipeline.py
│   ├── outputs/
│   │   ├── sales_facts.parquet
│   │   ├── customer_features.parquet
│   │   └── returns_log.parquet
│   ├── pipeline_log.txt
│   └── validation_report.md
│
├── q4_llm_extraction/
│   ├── extract_reviews.py
│   ├── prompt_template.txt
│   ├── extracted_issues.json
│   ├── pipeline_design.md
│   ├── cost_report.md
│   └── accuracy_evaluation.md
│
├── q5_system_design/
│   └── real_time_pipeline_design.md
│
└── bonus/
    ├── q6_1_ai_collaboration.md
    └── q6_2_business_insights.md
```

---


#### 完成度建议
- 在 `REFLECTION.md` 中**明确说明未完成的部分**和原因，**不会扣分**
- 故意留空但谎称完成 → 在面试追问时会被发现，反而扣分

---

### 🚫 注意事项

#### 关于 Fork 仓库
- 请**不要修改**根目录的题目文件 —— 只在指定模板中补充
- 请**不要 force push** 覆盖 commit 历史 —— 我们会看你的迭代过程
- **每个模块单独 commit**，commit message 要有意义（不要全是 "update"）

#### 关于诚信
- 我们**会在面试中追问代码细节** —— 任意一段代码都可能被问"为什么这么写"
- 如果你让 AI 生成代码但不完全理解，请在 `REFLECTION.md` 中**主动承认**：「这段是 AI 写的，我理解大致逻辑但未深究 XX 细节」 —— **这反而是加分项**
- 完全照抄网上现有项目 → 一旦被发现直接淘汰

#### 关于面试
- 通过笔试者将进入技术面试环节
- 面试会基于**你的提交代码**展开，请确保你能解释每一段实现
- 我们会重点询问 `REFLECTION.md` 中你提到的"踩坑"和"改进点"

---

### ❓ 常见问题

**Q: 我可以用我熟悉的语言（如 Scala/Go）做部分题目吗？**  
A: 数据处理建议用 Python（团队主语言）。SQL 题必须用 SQL。其他可灵活选择。

**Q: 我做到一半发现某道题做不出来，可以跳过吗？**  
A: 可以。在 `REFLECTION.md` 中说明：「这道题我尝试了 XX 方案但没成功，遇到的卡点是 XX」 —— 这本身就是有效信息。

**Q: 我能不能直接用 Cursor/Copilot 一边写一边用？**  
A: 完全可以。但请保留对话记录，并能解释最终代码。

---

# 🔍 模块 1：数据质量探索

**数据集**：Online Retail II

## Q1.1 数据质量初探

请用 Python 加载 `online_retail_ii.csv`，生成一份 `data_quality_report.md`，至少包含：

1. 各列的数据类型与缺失值比例
2. 数值列的分布概况（min / max / mean / std）
3. 字符串列的唯一值数量与高频值 TOP 10

**评分要点**：
- 不要直接调用 `df.describe()` 完事。请挑出**至少 5 个看起来"可疑"的现象**并文字描述（例如「Quantity 的最小值为 -80995，远超正常范围」）


---

## Q1.2 揭示数据的真实结构

这份数据中有几个**反直觉的事实**，需要你通过探索发现。请在 `findings.md` 中回答以下问题，每个问题都要给出**支持代码**和**简短解读**：

### 问题 1：`InvoiceNo` 不只是数字

观察 `InvoiceNo` 列，你会发现：
- 大部分是 6 位数字
- 有些以字母开头

**任务**：
- 找出所有非纯数字的 `InvoiceNo` 前缀，统计每种前缀的出现次数
- 解释每种前缀代表什么业务含义（**提示**：观察这些行的 Quantity / UnitPrice / Description 特征）
- 你认为这些非常规记录在做"销售总额"统计时应该如何处理？

### 问题 2：`StockCode` 也不只是产品

观察 `StockCode` 列，你会发现一些"非产品代码"，比如 `POST`、`M`、`D`、`AMAZONFEE`、`BANK CHARGES` 等。

**任务**：
- 找出所有**非纯数字、非"数字+字母"格式**的 StockCode（如 `POST` 而非 `85123A`）
- 每种代码代表什么？给出业务解读
- 这些记录占总行数和总金额的比例分别是多少？

### 问题 3：可疑的极端值

数据中存在以下令人困惑的记录：
- `Quantity = 80,995`（最大值）
- `Quantity = -80,995`（最小值）  
- `UnitPrice` 出现负值

**任务**：
- 找出这两条 Quantity 极值记录的完整信息，判断它们是**真实业务**还是**数据错误**
- UnitPrice 为负的记录有什么共同特征？业务上代表什么？
- 如果你是数据工程师，会保留还是删除这些记录？说明你的判断标准

### 问题 4：CustomerID 的"沉默大多数"

观察 `Customer ID` 列，你会发现**相当一部分记录**缺失客户 ID（自己算出确切比例）。

**任务**：
- 自己先算出缺失客户 ID 的记录占总行数的比例
- 再计算这部分缺失记录占**总金额**的比例（重点：和总行数比例对比）
- 缺失 CustomerID 的记录与有 CustomerID 的记录在以下维度上**有什么差异**？
  - 国家分布
  - 客单价  
  - 高频商品
- 你能推测这些"匿名"记录是什么人群吗？

---

## Q1.3 设计清洗策略

基于以上发现，写一段 **300-500 字** 的清洗策略文档（`cleaning_strategy.md`），回答：

1. **为不同的下游用途**设计不同的清洗方案：
   - 用途 A：销售总额统计 / 报表
   - 用途 B：客户分群（RFM 模型）
   - 用途 C：商品推荐模型

2. 哪些数据"看起来脏"但**实际上不该删除**？

3. 哪些清洗操作是**有损的**？你怎么决定要不要做？

> 💡 这道题没有标准答案，重点考察「针对业务做权衡」的能力。AI 会给你一个"通用清洗模板"，但好的答案应该体现你对**数据真实含义**的理解。

---

# 📊 模块 2：SQL 与业务分析

**数据集**：Olist（9 张表）

**准备工作**：本试卷**强制使用 MySQL 8.0+**（团队生产数据库，不允许用 SQLite 代替）。

1. 本地起 MySQL（推荐 Docker 一行命令）：
   ```bash
   docker run -d --name mysql8 -e MYSQL_ROOT_PASSWORD=root -p 3306:3306 mysql:8
   ```
2. 新建数据库并把 9 张 CSV 灌进去：
   ```sql
   CREATE DATABASE olist DEFAULT CHARACTER SET utf8mb4;
   ```
   ```python
   import pandas as pd
   from sqlalchemy import create_engine

   engine = create_engine(
       "mysql+pymysql://root:root@localhost:3306/olist?charset=utf8mb4"
   )

   tables = ["customers", "geolocation", "order_items", "order_payments",
             "order_reviews", "orders", "products", "sellers"]
   for t in tables:
       df = pd.read_csv(f"data/olist/olist_{t}_dataset.csv")
       df.to_sql(t, engine, if_exists="replace", index=False, chunksize=10000)

   # 翻译表名称不带 olist_ 前缀
   df = pd.read_csv("data/olist/product_category_name_translation.csv")
   df.to_sql("product_category_name_translation", engine,
             if_exists="replace", index=False)
   ```
3. 所有 `.sql` 文件请以 **MySQL 8.0 方言** 为准（窗口函数、`STR_TO_DATE`、`DATE_FORMAT` 等都已可用）。

## Q2.1 商品类别翻译完整性

`product_category_name_translation` 表把葡萄牙语类别名翻译成英文，但翻译**并不完整**。

**任务**：写一段 SQL，找出 `products` 表中存在、但在翻译表中**没有英文对照**的类别名，并统计每种类别对应多少个商品。

**进阶**：对于这些缺失翻译的类别，你会如何处理？给出 3 种方案及利弊。

---

## Q2.2 平台真实成交分析

Olist 数据有个常被忽视的问题：**订单状态不全是 "delivered"**。`orders.order_status` 有以下取值：
`delivered / shipped / canceled / unavailable / invoiced / processing / created / approved`

**任务**：写一段 SQL，输出以下指标，按月份维度：

| 字段 | 含义 |
|------|------|
| `month` | 订单月份（基于 `order_purchase_timestamp`） |
| `total_orders` | 总下单量 |
| `delivered_orders` | 成功送达的订单数 |
| `canceled_orders` | 取消订单数 |
| `cancel_rate` | 取消率（保留 2 位小数） |
| `delivered_gmv` | 已送达订单的 GMV（含 price + freight_value） |
| `avg_delivery_days` | 已送达订单的平均送达天数（下单到送达） |

**评分要点**：
- 正确连接 `orders` 和 `order_items`
- 正确处理 NULL 的送达时间
- GMV 计算口径正确（不要漏 `freight_value`）

---

## Q2.3 卖家维度分析

写一段 SQL，找出 **2017 年 GMV TOP 20 的卖家**，并输出每个卖家的：

| 字段 | 含义 |
|------|------|
| `seller_id` | 卖家 ID |
| `seller_state` | 卖家所在州 |
| `gmv_2017` | 2017 年 GMV |
| `order_count` | 订单数 |
| `unique_customers` | 不重复客户数 |
| `avg_review_score` | 平均评分 |
| `late_delivery_rate` | 延迟送达率（实际送达 > 预计送达日期 的比例） |
| `cancel_rate` | 取消订单率 |
| `state_rank` | 在所在州内的 GMV 排名 |

**评分要点**：
- 正确使用窗口函数（`ROW_NUMBER` / `RANK`）做州内排名
- 正确连接 reviews 表（评分要去重，一个订单可能多条评价）
- 「延迟送达率」的计算逻辑正确
- SQL 可读性，用 CTE 而非嵌套子查询

---

## Q2.4 慢查询优化

下面这条 SQL 在数据量增长 100 倍后运行时间从 2 秒变成了 5 分钟：

```sql
SELECT 
    c.customer_state,
    COUNT(DISTINCT o.order_id) AS orders,
    SUM(oi.price) AS revenue,
    AVG(r.review_score) AS avg_score
FROM orders o
LEFT JOIN customers c ON o.customer_id = c.customer_id
LEFT JOIN order_items oi ON o.order_id = oi.order_id
LEFT JOIN order_reviews r ON o.order_id = r.order_id
WHERE o.order_status = 'delivered'
  AND o.order_purchase_timestamp >= '2017-01-01'
  AND LOWER(c.customer_city) LIKE '%sao%'
GROUP BY c.customer_state
ORDER BY revenue DESC;
```

**任务**：
1. 指出**至少 3 个**性能问题（不只是说"加索引"，要说**为什么**）
2. 给出优化后的 SQL 或建议添加的索引
3. 这个 SQL 有一个**潜在的统计错误**——`SUM(oi.price)` 的结果可能不是你以为的「订单总收入」。为什么？


---

# 🔄 模块 3：数据管道实战

**数据集**：Online Retail II

## Q3.1 端到端 ETL Pipeline

构建一个 Python pipeline，把 `online_retail_ii.csv` 转换为**3 个干净的数据集**，分别对应**3 种下游用途**：

### 输出 1：`sales_facts.parquet`（用于 BI 报表）
- 只包含真实销售（剔除取消订单、坏账调整、非产品 StockCode）
- 字段：`invoice_no, stock_code, description, quantity, unit_price, total_amount, invoice_datetime, customer_id, country`
- `total_amount` = quantity × unit_price
- 数据类型规范（日期是 datetime、金额是 float、ID 是 string）

### 输出 2：`customer_features.parquet`（用于客户分群）
基于真实销售，对**每个有 CustomerID 的客户**计算 RFM 特征：
- `customer_id`
- `recency_days`：距离最后一次购买的天数（以数据集最后一天为基准）
- `frequency`：购买次数（独立 invoice 数）
- `monetary`：总消费金额
- `first_purchase_date`
- `last_purchase_date`
- `unique_products`：购买过的独立商品数
- `country`：客户主要国家
- `is_one_time_buyer`：是否只购买过一次（布尔）

### 输出 3：`returns_log.parquet`（用于退货分析）
- 只包含取消订单（InvoiceNo 以 'C' 开头）
- 字段同 sales_facts
- 额外字段 `matched_original_invoice`：尝试匹配每一条退货对应的原始销售记录（**关键**：基于 CustomerID + StockCode + |Quantity| 反向匹配最近的一笔正向销售）
- 如果匹配不到，该字段为 NULL，并在日志中记录

### 要求

1. **代码结构**：拆成至少 5 个函数（如 `load_data` / `filter_real_sales` / `compute_rfm` / `match_returns` / `validate_output`），不要写在一个 main 函数里
2. **异常处理**：每一步都要有日志输出和异常捕获
3. **数据校验**：每个输出都要写**断言（assertion）**校验关键字段（比如 `total_amount` 不能为负、`recency_days` 不能为负）
4. **可重现**：随机种子固定，相同输入应该产出相同输出
5. **性能**：禁止用 `iterrows()` / `apply` 循环全表（除非有充分理由）。100 万行应在 2 分钟内跑完

### 提交物（放在 `q3_etl_pipeline/` 目录下）
- `pipeline.py`
- `outputs/` 目录下的 3 个 parquet 文件
- `pipeline_log.txt`：完整运行日志
- `validation_report.md`：每个输出的关键统计指标（行数、空值率、关键分布）

> 💡 **关于"退货匹配"**：这是个真实生产环境的难题。一个退货 invoice `C536379` 含 `quantity=-5`，要找它对应的原始购买记录——同一客户、同一商品、`quantity=5`、且时间早于退货日期、且离退货时间最近。AI 能写出代码，但**匹配规则的细节**需要你思考：
> - 如果多笔正向销售符合条件，匹配哪一笔？
> - 如果客户买了 10 个、分两次退货各退 5 个怎么办？
> - 如果原单的 quantity 比退货的小怎么办？

---

# 🤖 模块 4：LLM 应用与文本处理

**数据集**：Olist `order_reviews` 表（含葡萄牙语评价文本）

## Q4.1 评价文本结构化抽取

`order_reviews` 表中有大量评价文本（`review_comment_message` 字段，**葡萄牙语**），但大部分以非结构化形式存在。我们想把这些评价转换成结构化数据，用于产品改进。

### 任务

构建一个 pipeline，对 `order_reviews` 中**评分 ≤ 3 分** 的差评（约 1-2 万条），抽取以下结构化信息：

```json
{
  "review_id": "...",
  "issues": [
    {
      "category": "delivery_late | wrong_product | quality_defect | missing_item | seller_communication | packaging | other",
      "severity": "low | medium | high",
      "evidence_quote": "原文中证明这个问题的句子（葡萄牙语）",
      "evidence_quote_en": "英文翻译"
    }
  ],
  "sentiment_score": -1.0 ~ 1.0,
  "actionable_for_seller": true | false,
  "confidence": 0.0 ~ 1.0
}
```

### 约束条件

- **成本预算**：$3 USD 总成本上限
- **时长**：40 分钟
- **不允许全部用 GPT-4 处理所有评论**（成本会爆，且没必要）

### 你需要决策

1. **分流策略**：哪些评论值得用大模型处理？哪些用规则/小模型？
   - 提示：很多"差评"其实只有"ruim"（差）一个词，不需要 LLM
   
2. **Prompt 设计**：
   - 怎么让 LLM 输出严格的 JSON（少不了写一个 Prompt 模板）
   - 葡萄牙语怎么处理？让 LLM 翻译还是用专门翻译模型？
   - 怎么避免幻觉（LLM 编造原文中没有的问题）？

3. **批处理**：单条请求 vs 批量请求的成本对比

4. **评估准确率**：
   - 你没有 ground truth，怎么验证抽取得对？
   - 抽样 30 条人工标注 → 对比？这个流程你怎么设计？

### 提交物（放在 `q4_llm_extraction/` 目录下）

- `extract_reviews.py`
- `prompt_template.txt`
- `extracted_issues.json`（处理结果）
- `pipeline_design.md`（300-500 字，解释你的决策）
- `cost_report.md`（实际花费、token 数、单条平均成本）
- `accuracy_evaluation.md`（你的准确率评估方法和结果）


---

# 🏗️ 模块 5：系统设计

## Q5.1 实时数据管道设计

**场景**：

Olist 当前的数据是离线 CSV 导出。现在业务需求是——卖家希望**实时**看到自己的订单情况、买家评价、物流异常。

请设计一个**实时数据架构**，满足：

- 订单状态变更后 **30 秒内** 反映在卖家后台
- 评价文本进来后 **1 分钟内** 触发情感分析 + LLM 抽取
- 物流异常（如某订单延迟超过预计时间）**自动报警**到卖家
- 历史数据查询（卖家想看过去 6 个月的成交曲线）**毫秒级响应**
- 当前数据规模：**10 万订单/天**，预计 2 年内增长到 **100 万订单/天**

### 你需要回答

1. **整体架构图**（文字描述或 ASCII art）：从订单产生 → 各种处理 → 最终展示，标出每个组件的角色
2. **数据存储选型**：哪些数据进 OLTP、哪些进 OLAP、哪些进消息队列、哪些进缓存？为什么？
3. **LLM 部分如何避免成本失控**：100 万订单/天，如果每条评价都过 LLM，年成本估算多少？怎么优化？
4. **三个最大的风险点**和应对方式

### 评分要点

- **不会得高分的回答**：罗列技术栈（"用 Kafka + Flink + ClickHouse + Redis"）但不解释为什么
- **会得高分的回答**：
  - 体现成本意识（10 万/天 vs 100 万/天的架构会不一样）
  - 主动指出方案的局限性
  - 给出"如果 XX 出问题，我会怎么处理"的预案

字数：800-1500 字 + 一张架构图

---

# ⭐ 加分题

## Q6.1 AI 协作反向分析

请选择本试卷中你认为**最有挑战的一道题**，做以下分析：

1. **完整记录** 你和 AI 的对话过程（截图或粘贴文本）
2. 你的**第一个 prompt** 是什么？AI 的回答有什么问题？
3. 你迭代了几轮 prompt？关键的修正点是什么？
4. **AI 的最终答案有什么错误或不足**？你是怎么发现并修正的？
5. 如果让你**再做一次同样的题**，你的第一个 prompt 会怎么写？

---

## Q6.2 真实业务洞察

在完成以上所有题目过程中，你应该已经对 Olist 和 Online Retail 这两份数据**相当熟悉了**。请回答：

**「如果你是 Olist 或这家英国电商的数据工程师，你会主动给业务方提出哪 3 个改进建议？」**

要求：
- 每个建议都要基于你在数据中观察到的**具体现象**
- 不要给"建议加强数据治理"这种空话
- 建议要**可执行**，并预估改进后的业务收益

字数：300-600 字

> 💡 这道题考察"数据敏感性"。优秀的数据工程师不只是被动接需求，而是能从数据中发现机会。

---

# 💡 最后给候选人的话

1. **数据驱动**：不要凭空写代码。先看数据，再写假设，再实现
2. **诚实使用 AI**：在 `AI_LOG.md` 中如实记录对话，在 `REFLECTION.md` 中主动承认你不完全理解的部分——**这是加分项不是减分项**
3. **暴露思考过程**：每个文档至少 1/3 篇幅写"我是怎么想的"
4. **遇到歧义**：自己做合理假设，**在代码或文档中写清楚**
5. **三份必填文档**：`REFLECTION.md`、`TOOLS.md`、`AI_LOG.md` 缺一不可
6. **面试会追问**：请确保你能解释每一段代码的实现思路

如有任何问题可直接回复邮件，期待你的提交！

—— Gekko Lab 数据工程团队

祝好运 ✨

---

