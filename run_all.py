from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import kagglehub


ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
OLIST_DIR = DATA_DIR / "olist"

ONLINE_RETAIL_DATASET = "mashlyn/online-retail-ii-uci"
OLIST_DATASET = "olistbr/brazilian-ecommerce"

ONLINE_RETAIL_TARGET = DATA_DIR / "online_retail_ii.csv"
ONLINE_RETAIL_SOURCE_NAMES = (
    "online_retail_II.csv",
    "online_retail_ii.csv",
)

OLIST_FILES = (
    "olist_customers_dataset.csv",
    "olist_geolocation_dataset.csv",
    "olist_order_items_dataset.csv",
    "olist_order_payments_dataset.csv",
    "olist_order_reviews_dataset.csv",
    "olist_orders_dataset.csv",
    "olist_products_dataset.csv",
    "olist_sellers_dataset.csv",
    "product_category_name_translation.csv",
)

PYTHON_STEPS = (
    ("Q1 数据质量探索", ROOT_DIR / "q1_data_quality" / "q1_code.py"),
    ("Q3 ETL Pipeline", ROOT_DIR / "q3_etl_pipeline" / "pipeline.py"),
    ("Q4 LLM 抽取", ROOT_DIR / "q4_llm_extraction" / "extract_reviews.py"),
)


def find_first_file(base_dir: Path, filenames: tuple[str, ...]) -> Path | None:
    """在 Kaggle 缓存目录中查找指定文件。"""
    for filename in filenames:
        matches = sorted(base_dir.rglob(filename))
        if matches:
            return matches[0]
    return None


def copy_dataset_file(source: Path, target: Path) -> None:
    """复制数据文件到题目约定路径。"""
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    print(f"[OK] {source.name} -> {target.relative_to(ROOT_DIR)}")


def ensure_online_retail() -> None:
    """使用 Kagglehub 下载并整理 Online Retail II。"""
    if ONLINE_RETAIL_TARGET.exists():
        print("[SKIP] data/online_retail_ii.csv 已存在。")
        return

    print("[DOWNLOAD] Online Retail II")
    downloaded_dir = Path(kagglehub.dataset_download(ONLINE_RETAIL_DATASET))
    source = find_first_file(downloaded_dir, ONLINE_RETAIL_SOURCE_NAMES)

    if source is None:
        raise FileNotFoundError(
            "未在 Kaggle 下载目录中找到 online_retail_II.csv。"
            "请手动下载后保存为 data/online_retail_ii.csv。"
        )

    copy_dataset_file(source, ONLINE_RETAIL_TARGET)


def ensure_olist() -> None:
    """使用 Kagglehub 下载并整理 Olist 9 张 CSV。"""
    missing_files = [filename for filename in OLIST_FILES if not (OLIST_DIR / filename).exists()]

    if not missing_files:
        print("[SKIP] data/olist/ 下 9 张 Olist CSV 已存在。")
        return

    print("[DOWNLOAD] Brazilian E-Commerce by Olist")
    OLIST_DIR.mkdir(parents=True, exist_ok=True)
    downloaded_dir = Path(kagglehub.dataset_download(OLIST_DATASET))

    for filename in missing_files:
        source = find_first_file(downloaded_dir, (filename,))
        if source is None:
            raise FileNotFoundError(f"未在 Kaggle 下载目录中找到 {filename}。")
        copy_dataset_file(source, OLIST_DIR / filename)


def ensure_data() -> None:
    """确保 README 要求的两份数据集都已经落到 data/ 目录。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ensure_online_retail()
    ensure_olist()


def run_python_step(step_name: str, script_path: Path) -> bool:
    """运行已实现的模块脚本；缺失脚本先跳过，避免阻塞其他模块。"""
    if not script_path.exists():
        print(f"[SKIP] {step_name}: 未找到 {script_path.relative_to(ROOT_DIR)}")
        return True

    print(f"[RUN] {step_name}: {script_path.relative_to(ROOT_DIR)}")
    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=ROOT_DIR,
        check=False,
    )

    if result.returncode == 0:
        print(f"[OK] {step_name} 完成。")
        return True

    print(f"[ERROR] {step_name} 失败，退出码：{result.returncode}", file=sys.stderr)
    return False


def run_available_modules() -> bool:
    """按 README 的一键入口约定运行当前已经实现的 Python 模块。"""
    results = [run_python_step(step_name, script_path) for step_name, script_path in PYTHON_STEPS]
    return all(results)


def main() -> int:
    print("========== 数据工程师笔试：一键运行 ==========")

    try:
        ensure_data()
    except Exception as exc:
        print(f"[ERROR] 数据准备失败：{exc}", file=sys.stderr)
        return 1

    print("========== 数据准备完成 ==========")

    if not run_available_modules():
        return 1

    print("========== 已完成当前可运行步骤 ==========")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
