# TOOLS.md - 工具与软件使用清单

本文只记录本次笔试中对解题、验证或复现有实质帮助的工具。`os`、`sys`、`pathlib`、`re` 等 Python 标准库不单独列出。

---

## AI 工具

### Codex / ChatGPT

- **版本/型号**：Codex / ChatGPT（GPT-5 系列，以当前平台显示为准）
- **解决了什么问题**：辅助拆解 Q1-Q5 的实现路径，把探索性结论整理成可提交的 Markdown，并协助检查代码、依赖和运行入口是否符合题目要求。
- **使用场景**：Q1 数据质量语义梳理、Q2 SQL 口径和执行计划分析、Q3 pipeline 结构设计、Q4 LLM 抽取链路和验证指标、Q5 实时架构文档、`requirements.txt` / `TOOLS.md` 的提交前整理。
- **替代方案**：完全手写代码和文档，并通过官方文档、Stack Overflow、MySQL Reference Manual、pandas 文档逐项核对。

### DeepSeek / OpenRouter

- **版本/型号**：DeepSeek provider，Small model 为 `deepseek-v4-flash`，Large model 为 `deepseek-v4-pro`；OpenRouter 作为 OpenAI-compatible 备用接入方式。
- **解决了什么问题**：验证 Q4 差评问题抽取 pipeline 的真实 LLM 调用路径、成本、失败率和 schema/evidence 校验策略。
- **使用场景**：Q4 full live 验证中处理 Olist 低分评论去重文本；默认提交入口仍使用 offline 模式，避免复现时需要 API key 或产生费用。
- **替代方案**：只使用规则引擎和人工抽样审核；或者换用其他支持 JSON 输出的 OpenAI-compatible 模型。

---

## 开发环境 / IDE

### PyCharm

- **解决了什么问题**：管理项目文件、运行脚本、查看 Markdown 和 Python 代码结构。
- **使用场景**：编辑 Q1-Q5 代码和报告，检查目录结构，配合终端运行 `run_all.py`、SQL 装载脚本和 pytest。
- **替代方案**：VS Code、Cursor、普通 Vim/Terminal 工作流。

### uv

- **版本**：`uv 0.11.7`
- **解决了什么问题**：统一 Python 解释器、依赖解析和 lock 文件，避免本地虚拟环境与提交依赖不一致。
- **使用场景**：`uv lock --python 3.10` 验证题目要求的 Python 3.10+ 口径；`uv tree` 查看当前解析出的直接依赖；`uv pip compile --python 3.10 requirements.txt` 检查 requirements 是否能解析。
- **替代方案**：`python -m venv` + `pip install -r requirements.txt`；如果要锁定传递依赖，可用 pip-tools。

### Jupyter Notebook

- **解决了什么问题**：支持 Q1 的探索式 EDA，便于边看数据边记录异常现象和业务解释。
- **使用场景**：早期分析 `online_retail_ii.csv` 的缺失值、取消单、坏账、库存损耗、商品组合等现象；后续再把稳定逻辑沉淀到 `q1_code.py`。
- **替代方案**：只用 Python 脚本输出 Markdown 报告；缺点是探索过程不如 Notebook 直观。

---

## 数据库工具

### MySQL 8.0+

- **解决了什么问题**：满足 Q2 强制使用 MySQL 8.0+ 的要求，并验证窗口函数、CTE、索引和执行计划。
- **使用场景**：把 Olist 9 张 CSV 装载到本地 `olist` 库，执行 Q2.1-Q2.4 SQL，并用 `EXPLAIN ANALYZE` 检查 Q2.4 的慢查询优化效果。
- **替代方案**：无直接替代方案，因为题目明确不允许用 SQLite / DuckDB 代替 MySQL；本地安装困难时可用 Docker 启动 MySQL 8。

### TablePlus

- **解决了什么问题**：可视化查看 MySQL 表结构、行数和查询结果，减少手写检查 SQL 的成本。
- **使用场景**：确认 Olist CSV 是否成功装载、检查字段类型、执行或复核 Q2 SQL 查询结果。
- **替代方案**：DBeaver、DataGrip、MySQL Workbench，或直接使用 `mysql` CLI。

---

## Python 库

### 数据处理

| 库 | 当前 uv 解析版本 | 用途 | 替代方案 |
|----|------------------|------|----------|
| pandas | 2.3.3 | Q1/Q3 数据清洗、分组聚合、时间字段处理、`merge_asof` 退货匹配、CSV 读写 | Polars；但本题数据量 pandas 足够，且团队更容易 review |
| numpy | 2.2.6 | Q3 中生成行号、数值辅助计算 | pandas 原生方法；但部分数组操作用 numpy 更直接 |
| pyarrow | 24.0.0 | Q3 输出 `sales_facts.parquet`、`customer_features.parquet`、`returns_log.parquet` | fastparquet；或输出 CSV，但题目要求 parquet 更适合下游分析 |

### 数据库 / SQL

| 库 | 当前 uv 解析版本 | 用途 | 替代方案 |
|----|------------------|------|----------|
| SQLAlchemy | 2.0.51 | 构造 MySQL 连接、用 `to_sql` 批量装载 Olist CSV、执行建库建索引 SQL | 直接用 PyMySQL cursor，但代码会更啰嗦 |
| PyMySQL | 1.2.0 | MySQL 8 纯 Python 驱动 | mysqlclient；性能更好但需要本地编译依赖 |
| cryptography | 49.0.0 | 支持 MySQL 8 默认 `caching_sha2_password` 认证 | 修改 MySQL 用户认证插件为 `mysql_native_password`，但不推荐 |

### 数据下载

| 库 | 当前 uv 解析版本 | 用途 | 替代方案 |
|----|------------------|------|----------|
| kagglehub | 1.0.2 | `run_all.py` 自动下载 Online Retail II 和 Olist 数据集 | 手动从 Kaggle 下载后解压到 `data/` |
| kagglesdk | 0.1.28 / 0.1.30 | kagglehub 的传递依赖；在 requirements 中用 Python 版本 marker 固定，避免 0.1.32 的 legacy 模块导入问题 | 不显式固定，让 kagglehub 自行解析；风险是不同 Python 版本可能拿到有问题的传递版本 |

### LLM / API

| 库 | 当前 uv 解析版本 | 用途 | 替代方案 |
|----|------------------|------|----------|
| openai | 2.44.0 | 使用 OpenAI-compatible client 调 DeepSeek / OpenRouter 的 chat completion JSON 输出 | 直接用 `requests` 调 REST API；或换用 provider 官方 SDK |
| pydantic | 2.13.4 | 定义并校验 Q4 抽取结果 schema，过滤 schema 错误和 evidence 错误 | 手写 JSON 校验；可控但更容易漏字段和类型错误 |
| python-dotenv | 1.2.2 | 从 `.env` 加载 `DEEPSEEK_API_KEY` / `OPENROUTER_API_KEY` | 直接使用 shell 环境变量 |

### 测试

| 库 | 当前 uv 解析版本 | 用途 | 替代方案 |
|----|------------------|------|----------|
| pytest | 9.1.1 | 跑 Q4 抽取逻辑测试和提交前回归检查 | Python 内置 `unittest`；语法更重 |

---

## 调试与分析工具

### pytest

- **解决了什么问题**：快速验证 Q4 的规则引擎、路由、schema 校验和 fallback 行为有没有回归。
- **使用场景**：修改 `q4_llm_extraction/extract_reviews.py` 后运行对应测试。
- **替代方案**：手写脚本抽样验证，但覆盖面和失败定位都更差。

### MySQL EXPLAIN ANALYZE

- **解决了什么问题**：把 Q2.4 的优化讨论从“理论上更快”变成有执行计划和耗时证据的分析。
- **使用场景**：比较原 SQL 和修正版 SQL 的扫描行数、临时表、CTE 物化、join 顺序和实际耗时。
- **替代方案**：只用 `EXPLAIN`；能看计划但缺少真实执行耗时。

### uv lock / uv tree / uv pip compile

- **解决了什么问题**：检查 `pyproject.toml`、`uv.lock`、`requirements.txt` 是否在 Python 3.10+ 口径下可解析。
- **使用场景**：发现 `kagglesdk==0.1.30` 与 Python 3.10 不兼容后，改成带 marker 的条件依赖。
- **替代方案**：手动读包元数据或在多个 Python 版本下创建 venv 安装；成本更高。

---

## 在线资源 / 文档

- **Pandas 官方文档**：核对 `groupby`、时间字段处理、`merge_asof` 和 parquet 输出行为。
- **MySQL 8.0 Reference Manual**：核对窗口函数、CTE、索引、`EXPLAIN ANALYZE` 和字符集相关语义。
- **Kaggle 数据集页面**：确认 Online Retail II 和 Brazilian E-Commerce by Olist 的数据来源与文件名。
- **DeepSeek / OpenRouter API 文档**：确认 OpenAI-compatible base URL、API key 环境变量和 JSON 输出调用方式。

---

## 关键工具决策反思

### 你做过的最重要的工具选型决策是？为什么？

最重要的决策是把不同模块放在最合适的执行工具里：Q1/Q3 使用 pandas，因为核心是清洗、派生字段和 parquet 输出；Q2 坚持 MySQL 8.0，因为题目明确要求 SQL 环境并且需要真实执行计划；Q4 使用 OpenAI-compatible SDK 接 DeepSeek/OpenRouter，因为可以复用统一 client，同时保留 offline 默认路径保证 `run_all.py` 可复现。

另一个关键决策是用 uv 检查依赖冲突。直接把当前 3.13 环境 freeze 到 requirements 会带入 Jupyter、可视化、Anthropic SDK 等不必要依赖，也会掩盖 Python 3.10 兼容性问题。改成按实际代码列直接依赖，再用 `uv lock --python 3.10` 验证，更符合提交要求。

### 你尝试过但放弃的工具/方案？

- **ucimlrepo**：最初模板里保留了它，但当前 `run_all.py` 已统一用 `kagglehub` 下载两份数据集，所以不再把它放进 requirements。
- **anthropic SDK**：Q4 最终只走 DeepSeek/OpenRouter 的 OpenAI-compatible 路径，没有直接调用 Claude API，因此不作为依赖。
- **langdetect / deep-translator**：Q4 数据本身来自 Olist 葡萄牙语评论，当前方案通过低分过滤、规则和 LLM 抽取处理，没有引入语言检测或翻译作为主链路。
- **loguru / tqdm / matplotlib / seaborn**：这些对体验有帮助，但当前可复现代码没有依赖它们；为了避免提交环境膨胀，未放进 requirements。
- **kagglesdk 0.1.32**：在当前环境可能触发 kagglehub legacy 模块导入问题，所以 requirements 用 marker 固定到 3.10 下的 0.1.28 和 3.11+ 下的 0.1.30。

### 如果再做一次，你会换用什么工具？

我会一开始就用 `pyproject.toml` + `uv.lock` 管理项目，避免一直捣鼓 pip。
