# Q3 Validation Report

## 1. Runtime Summary

| metric | value |
| --- | --- |
| input_rows | 1,067,371.00 |
| sales_facts_rows | 1,036,877.00 |
| customer_features_rows | 5,852.00 |
| returns_log_rows | 19,494.00 |
| eligible_return_rows | 17,933.00 |
| matched_eligible_returns | 6,509.00 |
| eligible_return_match_rate_pct | 36.30 |
| runtime_seconds | 2.20 |
| peak_memory_mb | 876.66 |

## 2. Sales Facts

Q3 uses Q1's gross product sales rule: numeric invoice, product-like StockCode, `Quantity > 0`, and `Price > 0`.

| measure | amount |
| --- | --- |
| gross_product_sales | 20,108,995.40 |
| net_product_sales | 19,382,476.01 |
| financial_total | 19,287,250.57 |
| q3_sales_facts_total_amount | 20,108,995.40 |
| q3_sales_facts_quantity_sum | 11,402,383.00 |

- Raw exact duplicate rows retained for audit sensitivity: 34,335
- Sales facts are sorted by `invoice_datetime`, `invoice_no`, `stock_code`, `customer_id`.

### Sales Facts Null Rates

| column | missing_rows | missing_pct |
| --- | --- | --- |
| invoice_no | 0 | 0.00 |
| stock_code | 0 | 0.00 |
| description | 0 | 0.00 |
| quantity | 0 | 0.00 |
| unit_price | 0 | 0.00 |
| total_amount | 0 | 0.00 |
| invoice_datetime | 0 | 0.00 |
| customer_id | 234,245 | 22.59 |
| country | 0 | 0.00 |

## 3. Customer Features

RFM uses identified customers only. Missing `Customer ID` rows stay in BI sales facts but are excluded from customer segmentation.

| metric | recency_days | frequency | monetary | unique_products |
| --- | --- | --- | --- | --- |
| count | 5,852.00 | 5,852.00 | 5,852.00 | 5,852.00 |
| mean | 199.20 | 6.25 | 2,979.23 | 82.19 |
| std | 208.51 | 12.75 | 14,604.97 | 116.49 |
| min | 0.00 | 1.00 | 2.95 | 1.00 |
| 25% | 24.00 | 1.00 | 344.98 | 19.00 |
| 50% | 94.00 | 3.00 | 880.38 | 45.00 |
| 75% | 378.00 | 7.00 | 2,289.34 | 103.00 |
| max | 738.00 | 373.00 | 608,821.65 | 2,546.00 |

### Customer Feature Null Rates

| column | missing_rows | missing_pct |
| --- | --- | --- |
| customer_id | 0 | 0.00 |
| recency_days | 0 | 0.00 |
| frequency | 0 | 0.00 |
| monetary | 0 | 0.00 |
| first_purchase_date | 0 | 0.00 |
| last_purchase_date | 0 | 0.00 |
| unique_products | 0 | 0.00 |
| country | 0 | 0.00 |
| is_one_time_buyer | 0 | 0.00 |

## 4. Returns Log

Returns log keeps all `C` invoice rows. Matching is conservative: same customer, same product StockCode, exact absolute quantity, original sale before the return, closest prior sale wins.

| status | rows |
| --- | --- |
| unmatched_no_exact_prior_sale | 11,424 |
| matched_exact_prior_sale | 6,509 |
| not_eligible_non_product_stock_code | 811 |
| not_eligible_missing_customer_id | 749 |
| not_eligible_non_negative_c_invoice | 1 |

### Returns Log Null Rates

| column | missing_rows | missing_pct |
| --- | --- | --- |
| invoice_no | 0 | 0.00 |
| stock_code | 0 | 0.00 |
| description | 0 | 0.00 |
| quantity | 0 | 0.00 |
| unit_price | 0 | 0.00 |
| total_amount | 0 | 0.00 |
| invoice_datetime | 0 | 0.00 |
| customer_id | 750 | 3.85 |
| country | 0 | 0.00 |
| matched_original_invoice | 12,985 | 66.61 |

### Unmatched Eligible Return Samples

| invoice_no | stock_code | description | quantity | unit_price | total_amount | invoice_datetime | customer_id | country |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C489449 | 21871 | SAVE THE PLANET MUG | -12 | 1.25 | -15.00 | 2009-12-01 10:33:00 | 16321 | Australia |
| C489449 | 21895 | POTTING SHED SOW 'N' GROW SET | -4 | 4.25 | -17.00 | 2009-12-01 10:33:00 | 16321 | Australia |
| C489449 | 21896 | POTTING SHED TWINE | -6 | 2.10 | -12.60 | 2009-12-01 10:33:00 | 16321 | Australia |
| C489449 | 22083 | PAPER CHAIN KIT RETRO SPOT | -12 | 2.95 | -35.40 | 2009-12-01 10:33:00 | 16321 | Australia |
| C489449 | 22087 | PAPER BUNTING WHITE LACE | -12 | 2.95 | -35.40 | 2009-12-01 10:33:00 | 16321 | Australia |
| C489449 | 22090 | PAPER BUNTING RETRO SPOTS | -12 | 2.95 | -35.40 | 2009-12-01 10:33:00 | 16321 | Australia |
| C489449 | 84946 | ANTIQUE SILVER TEA GLASS ETCHED | -12 | 1.25 | -15.00 | 2009-12-01 10:33:00 | 16321 | Australia |
| C489449 | 84970S | HANGING HEART ZINC T-LIGHT HOLDER | -24 | 0.85 | -20.40 | 2009-12-01 10:33:00 | 16321 | Australia |
| C489449 | 85206A | CREAM FELT EASTER EGG BASKET | -6 | 1.65 | -9.90 | 2009-12-01 10:33:00 | 16321 | Australia |
| C489459 | 90003B | ROSE COLOUR PAIR HEART HAIR SLIDES | -3 | 3.75 | -11.25 | 2009-12-01 10:44:00 | 17592 | United Kingdom |

## 5. Known Limitations

- Partial returns and split returns are intentionally unmatched when the original sale quantity differs from the return absolute quantity.
- The matching rule does not consume original sale quantities, so repeated exact return rows may point to the same closest prior sale.
- The one positive `C` invoice row in this dataset is kept in the cancellation log but marked as not eligible for return matching by the report status table.
