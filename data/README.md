# data/ - 数据集存放目录

本目录用于存放笔试所需的两份数据集 CSV 文件。**仓库不附带数据文件**，请按本文档自行下载。

## 📦 数据集来源

| 数据集 | Kaggle 链接 | 用于模块 |
|--------|-------------|----------|
| Online Retail II（UCI） | https://www.kaggle.com/datasets/mashlyn/online-retail-ii-uci | 模块 1（Q1）、模块 3（Q3） |
| Brazilian E-Commerce by Olist | https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce | 模块 2（Q2）、模块 4（Q4） |

## 📂 期望的目录结构

下载并解压后，本目录应该长这样（**题目代码以这些路径引用**）：

```
data/
├── README.md                                  # 本文件
├── .gitkeep                                   # 保留空目录
├── online_retail_ii.csv                       # Online Retail II（~45MB，约 106 万行）
└── olist/                                     # Olist 9 张表
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

## 🛠️ 下载方式（任选）

### 方式 A：用 `kagglehub`（推荐，可写进 `run_all.py`）

```python
import kagglehub, shutil, os

# Online Retail II
p1 = kagglehub.dataset_download("mashlyn/online-retail-ii-uci")
shutil.copy(os.path.join(p1, "online_retail_II.csv"), "data/online_retail_ii.csv")

# Olist
p2 = kagglehub.dataset_download("olistbr/brazilian-ecommerce")
os.makedirs("data/olist", exist_ok=True)
for f in os.listdir(p2):
    if f.endswith(".csv"):
        shutil.copy(os.path.join(p2, f), os.path.join("data/olist", f))
```

### 方式 B：Kaggle CLI

```bash
kaggle datasets download -d mashlyn/online-retail-ii-uci -p data/ --unzip
kaggle datasets download -d olistbr/brazilian-ecommerce  -p data/olist/ --unzip
```

### 方式 C：浏览器手动下载

到上面表格中的 Kaggle 页面点 **Download**，解压后按"期望的目录结构"摆放。

> 💡 **文件名注意**：Kaggle 原下载文件名是 `online_retail_II.csv`（大写 II），请**统一重命名**为 `online_retail_ii.csv`（小写）。题目代码、Q1/Q3 引用的都是小写文件名；在大小写敏感的 Linux/macOS 上不改名会找不到文件。

## ⚠️ 严禁提交数据集 CSV 到 Fork 仓库

- **GitHub 单文件上限 100MB**——大文件会直接被拒
- 仓库体积膨胀会让 reviewer 看你的 diff 很痛苦
- 根目录 `.gitignore` 已配好忽略规则，**请勿修改 `.gitignore` 来强行提交 CSV**
- 我们会在 review 时跑你的 `python run_all.py`，自行下载数据并复现 pipeline 产物

被忽略的路径包括：

```
data/*.csv
data/*.xlsx
data/*.parquet
data/olist/
data/Online Retail II*/
data/Brazilian E-Commerce*/
```

只有 `data/.gitkeep` 和本 `README.md` 会被提交。

## 🎯 检查清单

在开始写题之前，请确认：

- [ ] `data/online_retail_ii.csv` 存在且能用 pandas 读出 ~106 万行
- [ ] `data/olist/` 下有 9 个 CSV 文件
- [ ] `git status` 显示这些 CSV **没有**被加入暂存（被 `.gitignore` 忽略）
- [ ] 下载逻辑已经写进 `run_all.py` 或 `download_data.py`，新机器上能从 0 跑通
