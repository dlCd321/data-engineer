from __future__ import annotations

from dataclasses import dataclass
import os
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


@dataclass(frozen=True)
class PythonStep:
    name: str
    script_path: Path
    args: tuple[str, ...] = ()


@dataclass(frozen=True)
class RequiredArtifact:
    label: str
    path: Path


PYTHON_STEPS = (
    PythonStep("Q1 数据质量探索", ROOT_DIR / "q1_data_quality" / "q1_code.py"),
    PythonStep("Q3 ETL Pipeline", ROOT_DIR / "q3_etl_pipeline" / "pipeline.py"),
    PythonStep(
        "Q4 LLM 抽取",
        ROOT_DIR / "q4_llm_extraction" / "extract_reviews.py",
        (
            "--mode",
            "offline",
            "--no-write-docs",
        ),
    ),
)

Q2_MYSQL_STEP = PythonStep("Q2 Olist MySQL 装载", ROOT_DIR / "q2_sql_analysis" / "load_olist.py")
Q2_MYSQL_ENV_FLAG = "RUN_Q2_MYSQL_LOAD"

REQUIRED_ARTIFACTS = (
    RequiredArtifact("依赖锁定", ROOT_DIR / "requirements.txt"),
    RequiredArtifact("反思文档", ROOT_DIR / "REFLECTION.md"),
    RequiredArtifact("工具清单", ROOT_DIR / "TOOLS.md"),
    RequiredArtifact("AI 对话记录", ROOT_DIR / "AI_LOG.md"),
    RequiredArtifact("Q1 数据质量报告", ROOT_DIR / "q1_data_quality" / "data_quality_report.md"),
    RequiredArtifact("Q1 关键发现", ROOT_DIR / "q1_data_quality" / "findings.md"),
    RequiredArtifact("Q1 清洗策略", ROOT_DIR / "q1_data_quality" / "cleaning_strategy.md"),
    RequiredArtifact("Q2 MySQL 装载脚本", ROOT_DIR / "q2_sql_analysis" / "load_olist.py"),
    RequiredArtifact("Q2.1 SQL", ROOT_DIR / "q2_sql_analysis" / "q2_1_translation_gap.sql"),
    RequiredArtifact("Q2.2 SQL", ROOT_DIR / "q2_sql_analysis" / "q2_2_monthly_metrics.sql"),
    RequiredArtifact("Q2.3 SQL", ROOT_DIR / "q2_sql_analysis" / "q2_3_top_sellers.sql"),
    RequiredArtifact("Q2.4 优化文档", ROOT_DIR / "q2_sql_analysis" / "q2_4_query_optimization.md"),
    RequiredArtifact("Q3 pipeline", ROOT_DIR / "q3_etl_pipeline" / "pipeline.py"),
    RequiredArtifact("Q3 sales_facts", ROOT_DIR / "q3_etl_pipeline" / "outputs" / "sales_facts.parquet"),
    RequiredArtifact("Q3 customer_features", ROOT_DIR / "q3_etl_pipeline" / "outputs" / "customer_features.parquet"),
    RequiredArtifact("Q3 returns_log", ROOT_DIR / "q3_etl_pipeline" / "outputs" / "returns_log.parquet"),
    RequiredArtifact("Q3 运行日志", ROOT_DIR / "q3_etl_pipeline" / "pipeline_log.txt"),
    RequiredArtifact("Q3 校验报告", ROOT_DIR / "q3_etl_pipeline" / "validation_report.md"),
    RequiredArtifact("Q4 抽取脚本", ROOT_DIR / "q4_llm_extraction" / "extract_reviews.py"),
    RequiredArtifact("Q4 Prompt 模板", ROOT_DIR / "q4_llm_extraction" / "prompt_template.txt"),
    RequiredArtifact("Q4 抽取结果", ROOT_DIR / "q4_llm_extraction" / "extracted_issues.json"),
    RequiredArtifact("Q4 pipeline 设计", ROOT_DIR / "q4_llm_extraction" / "pipeline_design.md"),
    RequiredArtifact("Q4 成本报告", ROOT_DIR / "q4_llm_extraction" / "cost_report.md"),
    RequiredArtifact("Q4 准确率评估", ROOT_DIR / "q4_llm_extraction" / "accuracy_evaluation.md"),
    RequiredArtifact("Q5 实时管道设计", ROOT_DIR / "q5_system_design" / "real_time_pipeline_design.md"),
    RequiredArtifact("Q6.1 AI 协作分析", ROOT_DIR / "bonus" / "q6_1_ai_collaboration.md"),
    RequiredArtifact("Q6.2 业务洞察", ROOT_DIR / "bonus" / "q6_2_business_insights.md"),
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


def display_path(path: Path) -> Path:
    """优先显示仓库相对路径；仓库外路径保留绝对路径。"""
    try:
        return path.relative_to(ROOT_DIR)
    except ValueError:
        return path


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


def run_python_step(step: PythonStep) -> bool:
    """运行已实现的模块脚本；缺失脚本先跳过，避免阻塞其他模块。"""
    step_name = step.name
    script_path = step.script_path
    if not script_path.exists():
        print(f"[SKIP] {step_name}: 未找到 {display_path(script_path)}")
        return True

    display_args = f" {' '.join(step.args)}" if step.args else ""
    print(f"[RUN] {step_name}: {display_path(script_path)}{display_args}")
    result = subprocess.run(
        [sys.executable, str(script_path), *step.args],
        cwd=ROOT_DIR,
        check=False,
    )

    if result.returncode == 0:
        print(f"[OK] {step_name} 完成。")
        return True

    print(f"[ERROR] {step_name} 失败，退出码：{result.returncode}", file=sys.stderr)
    return False


def run_q2_mysql_load_if_requested() -> bool:
    """外部 MySQL 可用时，按 README 要求把 Olist CSV 装载到 MySQL。"""
    if os.getenv(Q2_MYSQL_ENV_FLAG) != "1":
        print(
            "[SKIP] Q2 MySQL 装载：未设置 "
            f"{Q2_MYSQL_ENV_FLAG}=1。SQL 文件会在提交物检查中校验。"
        )
        return True
    return run_python_step(Q2_MYSQL_STEP)


def run_available_modules() -> bool:
    """按 README 的一键入口约定运行当前已经实现的 Python 模块。"""
    results = [run_q2_mysql_load_if_requested()]
    results.extend(run_python_step(step) for step in PYTHON_STEPS)
    return all(results)


def artifact_has_content(path: Path) -> bool:
    return path.exists() and path.is_file() and path.stat().st_size > 0


def validate_required_artifacts() -> bool:
    """检查 README 要求的代码、SQL、文档和可复现输出是否齐全。"""
    print("========== 提交物完整性检查 ==========")
    ok = True
    for artifact in REQUIRED_ARTIFACTS:
        if artifact_has_content(artifact.path):
            print(f"[OK] {artifact.label}: {display_path(artifact.path)}")
            continue
        ok = False
        print(f"[ERROR] 缺少或为空：{artifact.label}: {display_path(artifact.path)}", file=sys.stderr)
    return ok


def main() -> int:
    print("========== 数据工程师笔试：一键运行 ==========")

    try:
        ensure_data()
    except Exception as exc:
        print(f"[ERROR] 数据准备失败：{exc}", file=sys.stderr)
        return 1

    print("========== 数据准备完成 ==========")

    modules_ok = run_available_modules()
    artifacts_ok = validate_required_artifacts()

    if not modules_ok or not artifacts_ok:
        return 1

    print("========== 已完成当前可运行步骤，并通过提交物检查 ==========")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
