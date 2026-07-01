from __future__ import annotations

import argparse
import logging
import resource
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, TypeVar

import numpy as np
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from q1_data_quality import q1_code as q1


Q3_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_PATH = ROOT_DIR / "data" / "online_retail_ii.csv"
DEFAULT_OUTPUT_DIR = Q3_DIR / "outputs"
DEFAULT_LOG_PATH = Q3_DIR / "pipeline_log.txt"
DEFAULT_REPORT_PATH = Q3_DIR / "validation_report.md"
RANDOM_SEED = 42

FACT_COLUMNS = [
    "invoice_no",
    "stock_code",
    "description",
    "quantity",
    "unit_price",
    "total_amount",
    "invoice_datetime",
    "customer_id",
    "country",
]
CUSTOMER_FEATURE_COLUMNS = [
    "customer_id",
    "recency_days",
    "frequency",
    "monetary",
    "first_purchase_date",
    "last_purchase_date",
    "unique_products",
    "country",
    "is_one_time_buyer",
]
RETURNS_COLUMNS = [*FACT_COLUMNS, "matched_original_invoice"]

classify_stock_code = q1.classify_stock_code

T = TypeVar("T")


@dataclass(frozen=True)
class PipelineResult:
    sales_facts_path: Path
    customer_features_path: Path
    returns_log_path: Path
    validation_report_path: Path
    log_path: Path
    runtime_seconds: float
    peak_memory_mb: float | None
    sales_rows: int
    customer_rows: int
    returns_rows: int
    matched_returns: int


def load_data(path: Path = DEFAULT_INPUT_PATH) -> pd.DataFrame:
    return q1.load_retail_data(path)


def normalize_columns(raw: pd.DataFrame) -> pd.DataFrame:
    rename_map = {
        source: target
        for source, target in q1.COLUMN_ALIASES.items()
        if source in raw.columns and source != target
    }
    normalized = raw.rename(columns=rename_map)
    required = [
        "Invoice",
        "StockCode",
        "Description",
        "Quantity",
        "InvoiceDate",
        "Price",
        "Customer ID",
        "Country",
    ]
    missing = [column for column in required if column not in normalized.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    return normalized[required].copy()


def classify_retail_rows(df: pd.DataFrame) -> pd.DataFrame:
    return q1.build_work_table(df)


def normalize_customer_id(values: pd.Series) -> pd.Series:
    as_text = values.astype("string").str.strip()
    as_number = pd.to_numeric(as_text, errors="coerce")
    normalized = as_number.astype("Int64").astype("string")
    return normalized.where(as_number.notna(), as_text.where(as_text.notna(), pd.NA))


def format_fact_columns(rows: pd.DataFrame) -> pd.DataFrame:
    result = pd.DataFrame(
        {
            "invoice_no": rows["InvoiceStr"].astype("string"),
            "stock_code": rows["StockCodeStr"].astype("string"),
            "description": rows["Description"].astype("string"),
            "quantity": pd.to_numeric(rows["Quantity"], errors="raise").astype("int64"),
            "unit_price": pd.to_numeric(rows["Price"], errors="raise").astype("float64"),
            "total_amount": pd.to_numeric(rows["LineAmount"], errors="raise").astype("float64"),
            "invoice_datetime": pd.to_datetime(rows["InvoiceDateParsed"]),
            "customer_id": normalize_customer_id(rows["Customer ID"]),
            "country": rows["Country"].astype("string"),
        }
    )
    return result[FACT_COLUMNS]


def sort_fact_rows(facts: pd.DataFrame) -> pd.DataFrame:
    return (
        facts.sort_values(
            ["invoice_datetime", "invoice_no", "stock_code", "customer_id"],
            na_position="last",
            kind="mergesort",
        )
        .reset_index(drop=True)
        .copy()
    )


def build_sales_facts(work: pd.DataFrame) -> pd.DataFrame:
    sales = format_fact_columns(work.loc[work["IsGrossProductSale"]])
    return sort_fact_rows(sales)


def primary_country_by_customer(sales: pd.DataFrame) -> pd.DataFrame:
    country_counts = (
        sales.dropna(subset=["customer_id"])
        .groupby(["customer_id", "country"], dropna=False)
        .size()
        .reset_index(name="country_rows")
        .sort_values(
            ["customer_id", "country_rows", "country"],
            ascending=[True, False, True],
            kind="mergesort",
        )
    )
    return country_counts.drop_duplicates("customer_id")[["customer_id", "country"]]


def compute_customer_features(
    sales_facts: pd.DataFrame,
    reference_datetime: pd.Timestamp,
) -> pd.DataFrame:
    identified = sales_facts.loc[sales_facts["customer_id"].notna()].copy()
    if identified.empty:
        return pd.DataFrame(columns=CUSTOMER_FEATURE_COLUMNS)

    grouped = (
        identified.groupby("customer_id", dropna=False)
        .agg(
            frequency=("invoice_no", "nunique"),
            monetary=("total_amount", "sum"),
            first_purchase_date=("invoice_datetime", "min"),
            last_purchase_date=("invoice_datetime", "max"),
            unique_products=("stock_code", "nunique"),
        )
        .reset_index()
    )
    grouped = grouped.assign(
        recency_days=(
            pd.to_datetime(reference_datetime) - grouped["last_purchase_date"]
        ).dt.days.astype("int64"),
        is_one_time_buyer=grouped["frequency"].eq(1).map(bool).astype(object),
    )
    features = grouped.merge(
        primary_country_by_customer(identified),
        on="customer_id",
        how="left",
    )
    features = features[
        [
            "customer_id",
            "recency_days",
            "frequency",
            "monetary",
            "first_purchase_date",
            "last_purchase_date",
            "unique_products",
            "country",
            "is_one_time_buyer",
        ]
    ]
    return (
        features.sort_values("customer_id", kind="mergesort")
        .reset_index(drop=True)
        .copy()
    )


def eligible_return_mask(returns: pd.DataFrame) -> pd.Series:
    product_like = returns["stock_code"].map(classify_stock_code).eq("product_like")
    return (
        returns["quantity"].lt(0)
        & returns["unit_price"].gt(0)
        & returns["customer_id"].notna()
        & product_like
    )


def match_returns_to_sales(
    returns: pd.DataFrame,
    sales_facts: pd.DataFrame,
) -> pd.Series:
    if returns.empty:
        return pd.Series(dtype="string")

    returns_with_ids = returns.reset_index(drop=True).assign(
        return_row_id=lambda df: np.arange(len(df), dtype="int64"),
        quantity_abs=lambda df: df["quantity"].abs().astype("int64"),
    )
    eligible = returns_with_ids.loc[eligible_return_mask(returns_with_ids)].copy()
    if eligible.empty:
        return pd.Series(pd.NA, index=returns.index, dtype="string")

    sales_candidates = (
        sales_facts.loc[sales_facts["customer_id"].notna()]
        .assign(
            quantity_abs=lambda df: df["quantity"].abs().astype("int64"),
            sale_invoice_datetime=lambda df: df["invoice_datetime"],
            matched_original_invoice=lambda df: df["invoice_no"].astype("string"),
        )[
            [
                "customer_id",
                "stock_code",
                "quantity_abs",
                "sale_invoice_datetime",
                "matched_original_invoice",
            ]
        ]
        .copy()
    )
    if sales_candidates.empty:
        return pd.Series(pd.NA, index=returns.index, dtype="string")

    left = eligible[
        [
            "return_row_id",
            "customer_id",
            "stock_code",
            "quantity_abs",
            "invoice_datetime",
        ]
    ].sort_values(
        ["invoice_datetime", "customer_id", "stock_code", "quantity_abs", "return_row_id"],
        kind="mergesort",
    )
    right = sales_candidates.sort_values(
        [
            "sale_invoice_datetime",
            "customer_id",
            "stock_code",
            "quantity_abs",
            "matched_original_invoice",
        ],
        kind="mergesort",
    )
    matched = pd.merge_asof(
        left,
        right,
        by=["customer_id", "stock_code", "quantity_abs"],
        left_on="invoice_datetime",
        right_on="sale_invoice_datetime",
        direction="backward",
        allow_exact_matches=False,
    )
    match_by_return_id = matched.set_index("return_row_id")["matched_original_invoice"]
    result = returns_with_ids["return_row_id"].map(match_by_return_id).astype("string")
    result.index = returns.index
    return result


def build_returns_log(work: pd.DataFrame, sales_facts: pd.DataFrame) -> pd.DataFrame:
    returns = format_fact_columns(work.loc[work["IsCancellation"]])
    returns = sort_fact_rows(returns)
    matched_original_invoice = match_returns_to_sales(returns, sales_facts)
    result = returns.assign(matched_original_invoice=matched_original_invoice)
    return result[RETURNS_COLUMNS].copy()


def validate_outputs(
    sales_facts: pd.DataFrame,
    customer_features: pd.DataFrame,
    returns_log: pd.DataFrame,
) -> None:
    assert list(sales_facts.columns) == FACT_COLUMNS, "sales_facts schema mismatch"
    assert list(customer_features.columns) == CUSTOMER_FEATURE_COLUMNS, (
        "customer_features schema mismatch"
    )
    assert list(returns_log.columns) == RETURNS_COLUMNS, "returns_log schema mismatch"

    assert sales_facts["quantity"].gt(0).all(), "sales_facts quantity must be positive"
    assert sales_facts["unit_price"].gt(0).all(), "sales_facts unit_price must be positive"
    assert sales_facts["total_amount"].gt(0).all(), (
        "sales_facts total_amount must be positive"
    )
    assert sales_facts["invoice_datetime"].notna().all(), (
        "sales_facts invoice_datetime cannot be null"
    )

    if not customer_features.empty:
        assert customer_features["customer_id"].notna().all(), (
            "customer_features customer_id cannot be null"
        )
        assert customer_features["recency_days"].ge(0).all(), (
            "customer_features recency_days must be nonnegative"
        )
        assert customer_features["frequency"].ge(1).all(), (
            "customer_features frequency must be at least 1"
        )
        assert customer_features["monetary"].ge(0).all(), (
            "customer_features monetary must be nonnegative"
        )

    if not returns_log.empty:
        assert returns_log["invoice_no"].astype("string").str.startswith("C").all(), (
            "returns_log must only contain C invoices"
        )
        matched = returns_log["matched_original_invoice"].dropna().astype("string")
        assert not matched.str.startswith("C").any(), (
            "matched_original_invoice must point to original positive sales"
        )


def scalar_to_text(value: object) -> str:
    if value is None or value is pd.NA:
        return ""
    if isinstance(value, float) and np.isnan(value):
        return ""
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, float):
        return f"{value:,.2f}"
    if isinstance(value, (int, np.integer)):
        return f"{int(value):,}"
    return str(value)


def dataframe_to_markdown(df: pd.DataFrame, max_rows: int = 20) -> str:
    if df.empty:
        return "_No rows._"
    display = df.head(max_rows).copy()
    columns = list(display.columns)
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    rows = [
        "| "
        + " | ".join(scalar_to_text(row[column]) for column in columns)
        + " |"
        for _, row in display.iterrows()
    ]
    if len(df) > max_rows:
        rows.append(f"| ... | {' | '.join('' for _ in columns[1:])} |")
    return "\n".join([header, separator, *rows])


def null_rate_table(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "column": df.columns,
            "missing_rows": [int(df[column].isna().sum()) for column in df.columns],
            "missing_pct": [
                round(float(df[column].isna().mean() * 100), 2) for column in df.columns
            ],
        }
    )


def output_summary_table(
    work: pd.DataFrame,
    sales_facts: pd.DataFrame,
    customer_features: pd.DataFrame,
    returns_log: pd.DataFrame,
    runtime_seconds: float,
    peak_memory_mb: float | None,
) -> pd.DataFrame:
    eligible = eligible_return_mask(returns_log)
    matched_eligible = eligible & returns_log["matched_original_invoice"].notna()
    return pd.DataFrame(
        [
            {"metric": "input_rows", "value": len(work)},
            {"metric": "sales_facts_rows", "value": len(sales_facts)},
            {"metric": "customer_features_rows", "value": len(customer_features)},
            {"metric": "returns_log_rows", "value": len(returns_log)},
            {"metric": "eligible_return_rows", "value": int(eligible.sum())},
            {"metric": "matched_eligible_returns", "value": int(matched_eligible.sum())},
            {
                "metric": "eligible_return_match_rate_pct",
                "value": round(float(matched_eligible.sum() / eligible.sum() * 100), 2)
                if int(eligible.sum())
                else 0.0,
            },
            {"metric": "runtime_seconds", "value": round(runtime_seconds, 2)},
            {
                "metric": "peak_memory_mb",
                "value": round(peak_memory_mb, 2) if peak_memory_mb is not None else "",
            },
        ]
    )


def sales_metric_table(work: pd.DataFrame, sales_facts: pd.DataFrame) -> pd.DataFrame:
    q1_sales = q1.sales_measure_summary(work)[["measure", "amount"]]
    q3_sales = pd.DataFrame(
        [
            {
                "measure": "q3_sales_facts_total_amount",
                "amount": sales_facts["total_amount"].sum(),
            },
            {
                "measure": "q3_sales_facts_quantity_sum",
                "amount": sales_facts["quantity"].sum(),
            },
        ]
    )
    return pd.concat([q1_sales, q3_sales], ignore_index=True)


def returns_status_table(returns_log: pd.DataFrame) -> pd.DataFrame:
    if returns_log.empty:
        return pd.DataFrame(columns=["status", "rows"])
    product_like = returns_log["stock_code"].map(classify_stock_code).eq("product_like")
    eligible = eligible_return_mask(returns_log)
    statuses = np.select(
        [
            returns_log["matched_original_invoice"].notna(),
            eligible & returns_log["matched_original_invoice"].isna(),
            returns_log["quantity"].ge(0),
            returns_log["customer_id"].isna(),
            ~product_like,
            returns_log["unit_price"].le(0),
        ],
        [
            "matched_exact_prior_sale",
            "unmatched_no_exact_prior_sale",
            "not_eligible_non_negative_c_invoice",
            "not_eligible_missing_customer_id",
            "not_eligible_non_product_stock_code",
            "not_eligible_non_positive_price",
        ],
        default="not_eligible_other",
    )
    return (
        pd.Series(statuses, name="status")
        .value_counts()
        .rename_axis("status")
        .reset_index(name="rows")
    )


def unmatched_return_samples(returns_log: pd.DataFrame, limit: int = 10) -> pd.DataFrame:
    eligible = eligible_return_mask(returns_log)
    unmatched = returns_log.loc[
        eligible & returns_log["matched_original_invoice"].isna(),
        [
            "invoice_no",
            "stock_code",
            "description",
            "quantity",
            "unit_price",
            "total_amount",
            "invoice_datetime",
            "customer_id",
            "country",
        ],
    ]
    return unmatched.sort_values(
        ["invoice_datetime", "invoice_no", "stock_code"],
        kind="mergesort",
    ).head(limit)


def write_validation_report(
    path: Path,
    work: pd.DataFrame,
    sales_facts: pd.DataFrame,
    customer_features: pd.DataFrame,
    returns_log: pd.DataFrame,
    runtime_seconds: float,
    peak_memory_mb: float | None,
) -> None:
    duplicate_rows = int(
        work[
            [
                "Invoice",
                "StockCode",
                "Description",
                "Quantity",
                "InvoiceDate",
                "Price",
                "Customer ID",
                "Country",
            ]
        ].duplicated().sum()
    )
    report = f"""# Q3 Validation Report

## 1. Runtime Summary

{dataframe_to_markdown(output_summary_table(work, sales_facts, customer_features, returns_log, runtime_seconds, peak_memory_mb))}

## 2. Sales Facts

Q3 uses Q1's gross product sales rule: numeric invoice, product-like StockCode, `Quantity > 0`, and `Price > 0`.

{dataframe_to_markdown(sales_metric_table(work, sales_facts))}

- Raw exact duplicate rows retained for audit sensitivity: {duplicate_rows:,}
- Sales facts are sorted by `invoice_datetime`, `invoice_no`, `stock_code`, `customer_id`.

### Sales Facts Null Rates

{dataframe_to_markdown(null_rate_table(sales_facts))}

## 3. Customer Features

RFM uses identified customers only. Missing `Customer ID` rows stay in BI sales facts but are excluded from customer segmentation.

{dataframe_to_markdown(customer_features[["recency_days", "frequency", "monetary", "unique_products"]].describe().reset_index().rename(columns={"index": "metric"}).round(2))}

### Customer Feature Null Rates

{dataframe_to_markdown(null_rate_table(customer_features))}

## 4. Returns Log

Returns log keeps all `C` invoice rows. Matching is conservative: same customer, same product StockCode, exact absolute quantity, original sale before the return, closest prior sale wins.

{dataframe_to_markdown(returns_status_table(returns_log))}

### Returns Log Null Rates

{dataframe_to_markdown(null_rate_table(returns_log))}

### Unmatched Eligible Return Samples

{dataframe_to_markdown(unmatched_return_samples(returns_log))}

## 5. Known Limitations

- Partial returns and split returns are intentionally unmatched when the original sale quantity differs from the return absolute quantity.
- The matching rule does not consume original sale quantities, so repeated exact return rows may point to the same closest prior sale.
- The one positive `C` invoice row in this dataset is kept in the cancellation log but marked as not eligible for return matching by the report status table.
"""
    path.write_text(report, encoding="utf-8")


def setup_logger(log_path: Path) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("q3_etl_pipeline")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    logger.propagate = False
    return logger


def run_step(name: str, logger: logging.Logger, action: Callable[[], T]) -> T:
    logger.info("START %s", name)
    try:
        result = action()
    except Exception:
        logger.exception("FAILED %s", name)
        raise
    logger.info("OK %s", name)
    return result


def peak_memory_mb() -> float | None:
    try:
        usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    except Exception:
        return None
    if sys.platform == "darwin":
        return usage / 1024 / 1024
    return usage / 1024


def write_outputs(
    output_dir: Path,
    sales_facts: pd.DataFrame,
    customer_features: pd.DataFrame,
    returns_log: pd.DataFrame,
) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    sales_path = output_dir / "sales_facts.parquet"
    customer_path = output_dir / "customer_features.parquet"
    returns_path = output_dir / "returns_log.parquet"
    sales_facts.to_parquet(sales_path, index=False)
    customer_features.to_parquet(customer_path, index=False)
    returns_log.to_parquet(returns_path, index=False)
    return sales_path, customer_path, returns_path


def run_pipeline(
    input_path: Path = DEFAULT_INPUT_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    log_path: Path = DEFAULT_LOG_PATH,
    report_path: Path = DEFAULT_REPORT_PATH,
) -> PipelineResult:
    np.random.seed(RANDOM_SEED)
    logger = setup_logger(log_path)
    started_at = time.perf_counter()
    logger.info("Q3 pipeline input=%s output_dir=%s", input_path, output_dir)

    try:
        raw = run_step("load_data", logger, lambda: load_data(input_path))
        work = run_step("classify_retail_rows", logger, lambda: classify_retail_rows(raw))
        sales_facts = run_step("build_sales_facts", logger, lambda: build_sales_facts(work))
        reference_datetime = pd.to_datetime(work["InvoiceDateParsed"]).max()
        customer_features = run_step(
            "compute_customer_features",
            logger,
            lambda: compute_customer_features(sales_facts, reference_datetime),
        )
        returns_log = run_step(
            "build_returns_log",
            logger,
            lambda: build_returns_log(work, sales_facts),
        )
        run_step(
            "validate_outputs",
            logger,
            lambda: validate_outputs(sales_facts, customer_features, returns_log),
        )
        sales_path, customer_path, returns_path = run_step(
            "write_parquet_outputs",
            logger,
            lambda: write_outputs(output_dir, sales_facts, customer_features, returns_log),
        )
        runtime_seconds = time.perf_counter() - started_at
        memory_mb = peak_memory_mb()
        run_step(
            "write_validation_report",
            logger,
            lambda: write_validation_report(
                report_path,
                work,
                sales_facts,
                customer_features,
                returns_log,
                runtime_seconds,
                memory_mb,
            ),
        )
    except Exception:
        logger.exception("Q3 pipeline failed")
        raise

    eligible = eligible_return_mask(returns_log)
    matched = int((eligible & returns_log["matched_original_invoice"].notna()).sum())
    logger.info(
        "DONE runtime_seconds=%.2f sales_rows=%s customer_rows=%s returns_rows=%s matched_eligible_returns=%s",
        runtime_seconds,
        len(sales_facts),
        len(customer_features),
        len(returns_log),
        matched,
    )
    return PipelineResult(
        sales_facts_path=sales_path,
        customer_features_path=customer_path,
        returns_log_path=returns_path,
        validation_report_path=report_path,
        log_path=log_path,
        runtime_seconds=runtime_seconds,
        peak_memory_mb=memory_mb,
        sales_rows=len(sales_facts),
        customer_rows=len(customer_features),
        returns_rows=len(returns_log),
        matched_returns=matched,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Q3 Online Retail II ETL outputs.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--log-path", type=Path, default=DEFAULT_LOG_PATH)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT_PATH)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_pipeline(
        input_path=args.input,
        output_dir=args.output_dir,
        log_path=args.log_path,
        report_path=args.report_path,
    )
    print(f"[OK] sales_facts: {result.sales_facts_path}")
    print(f"[OK] customer_features: {result.customer_features_path}")
    print(f"[OK] returns_log: {result.returns_log_path}")
    print(f"[OK] validation_report: {result.validation_report_path}")
    print(f"[OK] pipeline_log: {result.log_path}")
    print(f"[OK] runtime_seconds={result.runtime_seconds:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
