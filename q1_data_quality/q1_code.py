from __future__ import annotations

from collections import Counter
from itertools import combinations
import re
from pathlib import Path

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = REPO_ROOT / "data" / "online_retail_ii.csv"


COLUMN_ALIASES = {
    "InvoiceNo": "Invoice",
    "Invoice": "Invoice",
    "StockCode": "StockCode",
    "Description": "Description",
    "Quantity": "Quantity",
    "InvoiceDate": "InvoiceDate",
    "UnitPrice": "Price",
    "Price": "Price",
    "CustomerID": "Customer ID",
    "Customer ID": "Customer ID",
    "Country": "Country",
}


def pct(value: float, denominator: float) -> float:
    if denominator == 0:
        return np.nan
    return round(value / denominator * 100, 2)


def load_retail_data(path: Path = DATA_PATH) -> pd.DataFrame:
    df = pd.read_csv(path)
    rename_map = {
        source: target
        for source, target in COLUMN_ALIASES.items()
        if source in df.columns and source != target
    }
    normalized = df.rename(columns=rename_map)
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


def classify_stock_code(code_value: object) -> str:
    code = str(code_value).strip().upper()
    if code in {"POST", "DOT", "C2"}:
        return "postage_carriage_dotcom"
    if code == "D":
        return "discount"
    if code in {"M", "ADJUST", "ADJUST2"}:
        return "manual_adjustment"
    if code in {"BANK CHARGES", "AMAZONFEE", "CRUK", "B"}:
        return "fees_commission_bad_debt"
    if code.startswith("GIFT"):
        return "gift_voucher"
    if code in {"S", "TEST001", "TEST002", "PADS"} or code.startswith("DCGS"):
        return "sample_test_internal"
    if re.fullmatch(r"\d+[A-Z]*", code):
        return "product_like"
    return "other_non_product_or_unknown"


def build_work_table(df: pd.DataFrame) -> pd.DataFrame:
    work = df.assign(
        InvoiceStr=df["Invoice"].astype(str),
        StockCodeStr=df["StockCode"].astype(str).str.strip(),
        InvoiceDateParsed=pd.to_datetime(df["InvoiceDate"]),
        LineAmount=df["Quantity"] * df["Price"],
    )
    work = work.assign(
        InvoicePrefix=work["InvoiceStr"]
        .str.extract(r"^([A-Za-z]+)", expand=False)
        .fillna("numeric"),
        IsCancellation=work["InvoiceStr"].str.startswith("C", na=False),
        IsBadDebtAdjustment=work["InvoiceStr"].str.startswith("A", na=False),
        IsCustomerMissing=work["Customer ID"].isna(),
        IsDescriptionMissing=work["Description"].isna(),
        StockCodeCategory=work["StockCodeStr"].map(classify_stock_code),
    )
    work = work.assign(
        IsDamageOrInventoryLoss=(
            work["Price"].eq(0)
            & work["Quantity"].lt(0)
            & ~work["IsCancellation"]
            & ~work["IsBadDebtAdjustment"]
        ),
        IsProductLike=work["StockCodeCategory"].eq("product_like"),
    )
    return work.assign(
        IsGrossProductSale=(
            work["InvoicePrefix"].eq("numeric")
            & work["StockCodeCategory"].eq("product_like")
            & work["Quantity"].gt(0)
            & work["Price"].gt(0)
        ),
        IsNetProductLine=(
            work["StockCodeCategory"].eq("product_like")
            & ~work["IsBadDebtAdjustment"]
            & work["Price"].gt(0)
            & work["Quantity"].ne(0)
        ),
    )


def missing_value_report(df: pd.DataFrame) -> pd.DataFrame:
    return (
        pd.DataFrame(
            {
                "dtype": df.dtypes.astype(str),
                "missing_rows": df.isna().sum(),
                "missing_pct": (df.isna().mean() * 100).round(2),
            }
        )
        .reset_index()
        .rename(columns={"index": "column"})
    )


def string_profile(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    string_columns = [
        column
        for column in df.columns
        if pd.api.types.is_string_dtype(df[column])
        or pd.api.types.is_object_dtype(df[column])
    ]
    for column in string_columns:
        counts = df[column].astype("string").fillna("<missing>").value_counts().head(10)
        rows.append(
            {
                "column": column,
                "unique_values": int(df[column].nunique(dropna=True)),
                "top_10_values": "; ".join(
                    f"{index}: {value}" for index, value in counts.items()
                ),
            }
        )
    return pd.DataFrame(rows)


def invoice_prefix_summary(work: pd.DataFrame) -> pd.DataFrame:
    return (
        work.groupby("InvoicePrefix", dropna=False)
        .agg(
            rows=("Invoice", "size"),
            invoices=("InvoiceStr", "nunique"),
            quantity_sum=("Quantity", "sum"),
            amount_sum=("LineAmount", "sum"),
            negative_quantity_rows=("Quantity", lambda s: int((s < 0).sum())),
            negative_price_rows=("Price", lambda s: int((s < 0).sum())),
        )
        .reset_index()
    )


def stock_code_category_summary(work: pd.DataFrame) -> pd.DataFrame:
    total_rows = len(work)
    total_amount = work["LineAmount"].sum()
    summary = (
        work.groupby("StockCodeCategory")
        .agg(
            rows=("Invoice", "size"),
            distinct_codes=("StockCodeStr", "nunique"),
            amount_sum=("LineAmount", "sum"),
        )
        .reset_index()
    )
    return summary.assign(
        row_pct=(summary["rows"] / total_rows * 100).round(3),
        amount_pct=(summary["amount_sum"] / total_amount * 100).round(3),
    ).sort_values("rows", ascending=False)


def non_product_code_list(work: pd.DataFrame) -> pd.DataFrame:
    non_product = work.loc[~work["StockCodeCategory"].eq("product_like")]
    rows = []
    for category, group in non_product.groupby("StockCodeCategory"):
        rows.append(
            {
                "category": category,
                "distinct_codes": int(group["StockCodeStr"].nunique()),
                "codes": ", ".join(sorted(group["StockCodeStr"].astype(str).unique())),
            }
        )
    return pd.DataFrame(rows).sort_values("category")


def customer_missing_summary(work: pd.DataFrame) -> pd.DataFrame:
    total_rows = len(work)
    total_amount = work["LineAmount"].sum()
    rows = []
    for label, mask in [
        ("Customer ID missing", work["IsCustomerMissing"]),
        ("Customer ID present", ~work["IsCustomerMissing"]),
    ]:
        segment = work.loc[mask]
        rows.append(
            {
                "segment": label,
                "rows": len(segment),
                "row_pct": pct(len(segment), total_rows),
                "amount_sum": segment["LineAmount"].sum(),
                "amount_pct_of_net": pct(segment["LineAmount"].sum(), total_amount),
                "avg_line_amount": segment["LineAmount"].mean(),
                "median_line_amount": segment["LineAmount"].median(),
                "uk_pct": pct(segment["Country"].eq("United Kingdom").sum(), len(segment)),
                "positive_qty_price_rows": int(
                    (segment["Quantity"].gt(0) & segment["Price"].gt(0)).sum()
                ),
                "damage_loss_rows": int(segment["IsDamageOrInventoryLoss"].sum()),
            }
        )
    return pd.DataFrame(rows)


def customer_missing_bucket_summary(work: pd.DataFrame) -> pd.DataFrame:
    missing = work.loc[work["IsCustomerMissing"]]
    bucket_masks = [
        (
            "normal positive line: Quantity > 0 and Price > 0",
            missing["Quantity"].gt(0) & missing["Price"].gt(0),
        ),
        ("damage / inventory loss: Price = 0 and Quantity < 0", missing["IsDamageOrInventoryLoss"]),
        ("zero-price positive quantity", missing["Price"].eq(0) & missing["Quantity"].gt(0)),
        ("cancellation / return: C invoice", missing["IsCancellation"]),
        ("bad debt: A invoice", missing["IsBadDebtAdjustment"]),
    ]
    rows = []
    for label, mask in bucket_masks:
        segment = missing.loc[mask]
        rows.append(
            {
                "bucket": label,
                "rows": len(segment),
                "pct_of_missing_rows": pct(len(segment), len(missing)),
                "amount_sum": segment["LineAmount"].sum(),
            }
        )
    return pd.DataFrame(rows)


def invoice_customer_completeness(work: pd.DataFrame) -> pd.DataFrame:
    invoice_level = (
        work.groupby("InvoiceStr")
        .agg(
            rows=("Invoice", "size"),
            missing_customer_rows=("IsCustomerMissing", "sum"),
            amount_sum=("LineAmount", "sum"),
            has_dotcom_postage=(
                "StockCodeStr",
                lambda s: s.astype(str).str.upper().eq("DOT").any(),
            ),
            damage_loss_rows=("IsDamageOrInventoryLoss", "sum"),
        )
        .reset_index()
    )
    invoice_level = invoice_level.assign(
        customer_id_pattern=np.select(
            [
                invoice_level["missing_customer_rows"].eq(0),
                invoice_level["missing_customer_rows"].eq(invoice_level["rows"]),
            ],
            ["all_present", "all_missing"],
            default="mixed_missing_present",
        )
    )
    summary = (
        invoice_level.groupby("customer_id_pattern")
        .agg(
            invoices=("InvoiceStr", "size"),
            rows=("rows", "sum"),
            amount_sum=("amount_sum", "sum"),
            dotcom_postage_invoices=("has_dotcom_postage", "sum"),
            damage_loss_invoices=("damage_loss_rows", lambda s: int((s > 0).sum())),
        )
        .reset_index()
    )
    return summary.assign(
        invoice_pct=(summary["invoices"] / summary["invoices"].sum() * 100).round(2),
        row_pct=(summary["rows"] / len(work) * 100).round(2),
    )


def sales_measure_summary(work: pd.DataFrame) -> pd.DataFrame:
    gross = work.loc[work["IsGrossProductSale"], "LineAmount"].sum()
    net = work.loc[work["IsNetProductLine"], "LineAmount"].sum()
    financial = work["LineAmount"].sum()
    return pd.DataFrame(
        [
            {
                "measure": "gross_product_sales",
                "amount": gross,
                "interpretation": "positive product sales only; best headline sales metric",
            },
            {
                "measure": "net_product_sales",
                "amount": net,
                "interpretation": "product sales after C-invoice returns/cancellations",
            },
            {
                "measure": "financial_total",
                "amount": financial,
                "interpretation": "all line amounts, including postage, fees, discounts, bad debt",
            },
        ]
    )


def gross_product_invoice_basket_sizes(work: pd.DataFrame) -> pd.DataFrame:
    invoice_items = (
        work.loc[work["IsGrossProductSale"]]
        .groupby("InvoiceStr")["StockCodeStr"]
        .agg(lambda s: len(set(s.astype(str))))
    )
    quantiles = invoice_items.quantile([0.5, 0.75, 0.9, 0.95, 0.99])
    return pd.DataFrame(
        [
            {
                "gross_product_invoices": int(invoice_items.size),
                "median_unique_products": quantiles.loc[0.5],
                "p75_unique_products": quantiles.loc[0.75],
                "p90_unique_products": quantiles.loc[0.9],
                "p95_unique_products": quantiles.loc[0.95],
                "p99_unique_products": quantiles.loc[0.99],
                "max_unique_products": int(invoice_items.max()),
                "invoices_with_50_plus_products": int(invoice_items.ge(50).sum()),
                "pct_invoices_with_50_plus_products": pct(
                    invoice_items.ge(50).sum(), invoice_items.size
                ),
            }
        ]
    )


def product_description_lookup(product_lines: pd.DataFrame) -> dict[str, str]:
    descriptions = (
        product_lines.dropna(subset=["Description"])
        .assign(DescriptionClean=lambda df: df["Description"].astype(str).str.strip())
        .groupby("StockCodeStr")["DescriptionClean"]
        .agg(lambda s: s.value_counts().index[0] if len(s) else "")
    )
    return descriptions.to_dict()


def product_pair_association_summary(
    work: pd.DataFrame,
    min_item_invoices: int = 200,
    min_pair_invoices: int = 100,
) -> pd.DataFrame:
    product_lines = work.loc[
        work["IsGrossProductSale"], ["InvoiceStr", "StockCodeStr", "Description"]
    ].copy()
    invoice_items = product_lines.groupby("InvoiceStr")["StockCodeStr"].agg(
        lambda s: tuple(sorted(set(s.astype(str))))
    )
    basket_sizes = invoice_items.map(len)
    invoice_count = len(invoice_items)

    item_counts: Counter[str] = Counter()
    for items in invoice_items:
        item_counts.update(items)

    frequent_items = {
        item for item, count in item_counts.items() if count >= min_item_invoices
    }
    pair_counts: Counter[tuple[str, str]] = Counter()
    large_basket_pair_counts: Counter[tuple[str, str]] = Counter()
    for invoice, items in invoice_items.items():
        filtered_items = [item for item in items if item in frequent_items]
        if len(filtered_items) < 2:
            continue
        is_large_basket = basket_sizes.loc[invoice] >= 50
        for pair in combinations(filtered_items, 2):
            pair_counts[pair] += 1
            if is_large_basket:
                large_basket_pair_counts[pair] += 1

    descriptions = product_description_lookup(product_lines)
    rows = []
    for (left, right), pair_invoice_count in pair_counts.items():
        if pair_invoice_count < min_pair_invoices:
            continue
        left_count = item_counts[left]
        right_count = item_counts[right]
        left_to_right_conf = pair_invoice_count / left_count
        right_to_left_conf = pair_invoice_count / right_count
        support = pair_invoice_count / invoice_count
        rows.append(
            {
                "left_code": left,
                "left_description": descriptions.get(left, ""),
                "right_code": right,
                "right_description": descriptions.get(right, ""),
                "pair_invoices": pair_invoice_count,
                "support_pct": support * 100,
                "left_to_right_conf_pct": left_to_right_conf * 100,
                "right_to_left_conf_pct": right_to_left_conf * 100,
                "lift": support / ((left_count / invoice_count) * (right_count / invoice_count)),
                "kulczynski_pct": (left_to_right_conf + right_to_left_conf) / 2 * 100,
                "all_confidence_pct": min(left_to_right_conf, right_to_left_conf) * 100,
                "imbalance_ratio": abs(left_count - right_count)
                / (left_count + right_count - pair_invoice_count),
                "large_basket_pair_pct": pct(
                    large_basket_pair_counts[(left, right)], pair_invoice_count
                ),
            }
        )
    return pd.DataFrame(rows)


def quality_flag_association_summary(work: pd.DataFrame) -> pd.DataFrame:
    flags = pd.DataFrame(
        {
            "CustomerID_missing": work["IsCustomerMissing"],
            "Description_missing": work["IsDescriptionMissing"],
            "Damage_inventory_loss": work["IsDamageOrInventoryLoss"],
            "Cancellation_C_invoice": work["IsCancellation"],
            "Bad_debt_A_invoice": work["IsBadDebtAdjustment"],
            "Non_product_stockcode": ~work["IsProductLike"],
            "Zero_price": work["Price"].eq(0),
            "Negative_quantity": work["Quantity"].lt(0),
            "Positive_product_sale": work["IsGrossProductSale"],
        }
    )
    total_rows = len(flags)
    rows = []
    for left, right in combinations(flags.columns, 2):
        left_count = int(flags[left].sum())
        right_count = int(flags[right].sum())
        both_count = int((flags[left] & flags[right]).sum())
        if both_count == 0:
            continue
        left_conf = both_count / left_count
        right_conf = both_count / right_count
        rows.append(
            {
                "left_flag": left,
                "right_flag": right,
                "left_rows": left_count,
                "right_rows": right_count,
                "both_rows": both_count,
                "support_pct": both_count / total_rows * 100,
                "left_to_right_conf_pct": left_conf * 100,
                "right_to_left_conf_pct": right_conf * 100,
                "lift": both_count * total_rows / (left_count * right_count),
                "kulczynski_pct": (left_conf + right_conf) / 2 * 100,
            }
        )
    return pd.DataFrame(rows)


def invoice_pattern_association_summary(work: pd.DataFrame) -> pd.DataFrame:
    invoice_source = work.assign(
        GrossProductStockCode=work["StockCodeStr"].where(work["IsGrossProductSale"])
    )
    invoice_level = (
        invoice_source.groupby("InvoiceStr")
        .agg(
            country=("Country", lambda s: s.mode().iat[0] if not s.mode().empty else s.iloc[0]),
            all_missing=("IsCustomerMissing", "all"),
            any_dot=("StockCodeStr", lambda s: s.astype(str).str.upper().eq("DOT").any()),
            any_damage=("IsDamageOrInventoryLoss", "any"),
            any_non_product=("IsProductLike", lambda s: (~s).any()),
            any_bad_debt=("IsBadDebtAdjustment", "any"),
            gross_unique_products=("GrossProductStockCode", lambda s: s.dropna().nunique()),
        )
        .reset_index()
    )
    invoice_flags = invoice_level.assign(
        large_basket_50plus=invoice_level["gross_unique_products"].ge(50),
        UK=invoice_level["country"].eq("United Kingdom"),
        Germany=invoice_level["country"].eq("Germany"),
        France=invoice_level["country"].eq("France"),
        EIRE=invoice_level["country"].eq("EIRE"),
    )
    flag_columns = [
        "all_missing",
        "any_dot",
        "any_damage",
        "any_non_product",
        "any_bad_debt",
        "large_basket_50plus",
        "UK",
        "Germany",
        "France",
        "EIRE",
    ]
    total_invoices = len(invoice_flags)
    rows = []
    for left, right in combinations(flag_columns, 2):
        left_count = int(invoice_flags[left].sum())
        right_count = int(invoice_flags[right].sum())
        both_count = int((invoice_flags[left] & invoice_flags[right]).sum())
        if both_count == 0:
            continue
        left_conf = both_count / left_count
        right_conf = both_count / right_count
        rows.append(
            {
                "left_pattern": left,
                "right_pattern": right,
                "left_invoices": left_count,
                "right_invoices": right_count,
                "both_invoices": both_count,
                "support_pct": both_count / total_invoices * 100,
                "left_to_right_conf_pct": left_conf * 100,
                "right_to_left_conf_pct": right_conf * 100,
                "lift": both_count * total_invoices / (left_count * right_count),
                "kulczynski_pct": (left_conf + right_conf) / 2 * 100,
            }
        )
    return pd.DataFrame(rows)


def print_section(title: str, value: pd.DataFrame | pd.Series | str) -> None:
    print(f"\n=== {title} ===")
    if isinstance(value, pd.DataFrame):
        show_index = not isinstance(value.index, pd.RangeIndex)
        print(value.to_string(index=show_index))
    elif isinstance(value, pd.Series):
        print(value.to_string())
    else:
        print(value)

def stock_codes_with_all_missing_description(work: pd.DataFrame) -> pd.DataFrame:
    result = (
        work.groupby("StockCodeStr")
        .agg(
            rows=("Invoice", "size"),
            missing_description_rows=("Description", lambda s: s.isna().sum()),
            all_description_missing=("Description", lambda s: s.isna().all()),
            stock_code_category=("StockCodeCategory", lambda s: s.mode().iat[0]),
        )
        .reset_index()
    )
    return result.loc[result["all_description_missing"]].sort_values("rows", ascending=False)
def main() -> None:
    df = load_retail_data()
    work = build_work_table(df)

    print_section(
        "dataset shape",
        f"rows={len(df):,}, columns={len(df.columns)}, net_line_amount={work['LineAmount'].sum():,.2f}",
    )
    print_section("missing value report", missing_value_report(df))
    print_section("numeric distribution", df[["Quantity", "Price"]].describe().round(2))
    print_section("string profile", string_profile(df))
    print_section("invoice prefix summary", invoice_prefix_summary(work).round(2))
    print_section("stock code category summary", stock_code_category_summary(work).round(3))
    print_section("non-product stock code list", non_product_code_list(work))
    print_section("sales measure summary", sales_measure_summary(work).round(2))
    print_section("gross product invoice basket sizes", gross_product_invoice_basket_sizes(work))
    product_pair_rules = product_pair_association_summary(work)
    print_section(
        "top product pair associations by support",
        product_pair_rules.sort_values(
            ["pair_invoices", "lift"], ascending=[False, False]
        )
        .head(12)
        .reset_index(drop=True)
        .round(2),
    )
    print_section(
        "top balanced product pair associations by lift",
        product_pair_rules.loc[
            product_pair_rules["all_confidence_pct"].ge(20)
            & product_pair_rules["imbalance_ratio"].le(0.5)
        ]
        .sort_values(["lift", "pair_invoices"], ascending=[False, False])
        .head(12)
        .reset_index(drop=True)
        .round(2),
    )
    quality_flag_rules = quality_flag_association_summary(work)
    print_section(
        "quality flag associations by lift",
        quality_flag_rules.sort_values(["lift", "both_rows"], ascending=[False, False])
        .head(15)
        .reset_index(drop=True)
        .round(3),
    )
    invoice_pattern_rules = invoice_pattern_association_summary(work)
    print_section(
        "invoice-level pattern associations by lift",
        invoice_pattern_rules.sort_values(
            ["lift", "both_invoices"], ascending=[False, False]
        )
        .head(15)
        .reset_index(drop=True)
        .round(3),
    )
    print_section(
        "quantity extreme rows",
        work.loc[
            work["Quantity"].isin([work["Quantity"].max(), work["Quantity"].min()]),
            [
                "Invoice",
                "StockCode",
                "Description",
                "Quantity",
                "InvoiceDate",
                "Price",
                "Customer ID",
                "Country",
                "LineAmount",
            ],
        ],
    )
    print_section(
        "negative price rows",
        work.loc[
            work["Price"].lt(0),
            [
                "Invoice",
                "StockCode",
                "Description",
                "Quantity",
                "InvoiceDate",
                "Price",
                "Customer ID",
                "Country",
                "LineAmount",
            ],
        ],
    )
    print_section(
        "stock codes with all missing descriptions",
        stock_codes_with_all_missing_description(work),
    )
    print_section(
        "damage and inventory loss description top 20",
        work.loc[work["IsDamageOrInventoryLoss"], "Description"]
        .fillna("<missing>")
        .str.upper()
        .value_counts()
        .head(20),
    )
    print_section("customer missing summary", customer_missing_summary(work).round(2))
    print_section(
        "customer missing bucket summary",
        customer_missing_bucket_summary(work).round(2),
    )
    print_section("invoice customer completeness", invoice_customer_completeness(work).round(2))
    print_section(
        "top stock codes/descriptions among missing Customer ID",
        work.loc[work["IsCustomerMissing"]]
        .groupby(["StockCodeStr", "Description"], dropna=False)
        .agg(
            rows=("Invoice", "size"),
            amount_sum=("LineAmount", "sum"),
            quantity_sum=("Quantity", "sum"),
        )
        .sort_values("rows", ascending=False)
        .head(15)
        .reset_index()
        .round(2),
    )
    print_section(
        "duplicate and date checks",
        pd.DataFrame(
            [
                {
                    "exact_duplicate_rows": int(df.duplicated(subset=df.columns.tolist()).sum()),
                    "description_missing_rows": int(work["IsDescriptionMissing"].sum()),
                    "description_missing_customer_missing_rows": int(
                        (work["IsDescriptionMissing"] & work["IsCustomerMissing"]).sum()
                    ),
                    "description_missing_damage_loss_rows": int(
                        (work["IsDescriptionMissing"] & work["IsDamageOrInventoryLoss"]).sum()
                    ),
                    "min_invoice_date": work["InvoiceDateParsed"].min(),
                    "max_invoice_date": work["InvoiceDateParsed"].max(),
                }
            ]
        ),
    )


if __name__ == "__main__":
    main()
