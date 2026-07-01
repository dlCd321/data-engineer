# Q2.4 - 慢查询优化分析

## 原始 SQL

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

---

## 第 1 问：性能问题分析（至少 3 个）

### 问题 1：

`LOWER(c.customer_city) LIKE '%sao%'` 很难走普通 BTree 索引。

- `LOWER()` 对列做函数计算，普通 `customer_city` 索引无法直接使用。
- 前置通配符 `%sao%` 不是左前缀匹配，即使用了函数索引，也通常不能像 `LIKE 'sao%'` 一样高效定位范围。
- 数据量放大 100 倍后，这一步会迫使 MySQL 扫描大量客户行，再参与后续 JOIN。

### 问题 2：

一对多 JOIN 会制造很大的中间结果。

- `orders -> order_items` 是一对多，一个订单可能多件商品。
- `orders -> order_reviews` 也可能一对多，Olist 中存在一个订单多条评价。
- 原 SQL 同时 JOIN 两张一对多表，会形成 `订单商品行数 * 评价行数` 的中间表；后续 `GROUP BY`、`COUNT(DISTINCT)`、`SUM()` 都要在放大的结果上执行。

### 问题 3：

过滤和聚合顺序不理想。

- 原 SQL 先 JOIN 明细和评价，再按州聚合；更合理的方式是先筛选订单和客户，再把 `order_items`、`order_reviews` 各自预聚合到订单粒度。
- `COUNT(DISTINCT o.order_id)` 是为了抵消 JOIN 后的重复订单，但这会引入额外去重成本，数据量大时容易使用临时表和 filesort。
- `ORDER BY revenue DESC` 依赖聚合结果，无法通过普通索引直接避免排序。

### 问题 4：

索引不完整或字段顺序不匹配会导致大表扫描。

- `orders` 需要同时按 `order_status`、`order_purchase_timestamp` 过滤，并用 `customer_id`、`order_id` JOIN。
- `order_items` 和 `order_reviews` 需要按 `order_id` 快速回表或聚合。
- `customers` 需要按城市筛选并连接 `customer_id`；如果城市搜索不能改为可索引模式，至少要先尽量减少参与 JOIN 的订单行。

---

## 第 2 问：优化方案

### 优化后的 SQL

```sql
WITH filtered_customers AS (
    SELECT
        c.customer_id,
        c.customer_state
    FROM customers AS c
    WHERE LOWER(c.customer_city) LIKE '%sao%'
),
filtered_orders AS (
    SELECT
        o.order_id,
        fc.customer_state
    FROM orders AS o
    INNER JOIN filtered_customers AS fc
        ON o.customer_id = fc.customer_id
    WHERE o.order_status = 'delivered'
      AND o.order_purchase_timestamp >= '2017-01-01'
),
item_revenue_by_order AS (
    SELECT
        oi.order_id,
        SUM(oi.price) AS order_revenue
    FROM order_items AS oi
    INNER JOIN filtered_orders AS fo
        ON oi.order_id = fo.order_id
    GROUP BY
        oi.order_id
),
review_by_order AS (
    SELECT
        r.order_id,
        AVG(r.review_score) AS order_avg_score
    FROM order_reviews AS r
    INNER JOIN filtered_orders AS fo
        ON r.order_id = fo.order_id
    GROUP BY
        r.order_id
)
SELECT
    fo.customer_state,
    COUNT(*) AS orders,
    ROUND(SUM(COALESCE(ir.order_revenue, 0)), 2) AS revenue,
    ROUND(AVG(rbo.order_avg_score), 2) AS avg_score
FROM filtered_orders AS fo
LEFT JOIN item_revenue_by_order AS ir
    ON fo.order_id = ir.order_id
LEFT JOIN review_by_order AS rbo
    ON fo.order_id = rbo.order_id
GROUP BY
    fo.customer_state
ORDER BY
    revenue DESC;
```

### 建议添加的索引

```sql
CREATE INDEX idx_orders_status_purchase_customer_order
    ON orders(order_status, order_purchase_timestamp, customer_id, order_id);

CREATE INDEX idx_customers_city_customer_state
    ON customers(customer_city, customer_id, customer_state);

CREATE INDEX idx_order_items_order_id
    ON order_items(order_id);

CREATE INDEX idx_order_reviews_order_id
    ON order_reviews(order_id);
```

如果业务必须长期做「城市名包含 sao」这类 substring 搜索，可以考虑：

- 把城市名标准化为小写/去重音的生成列，例如 `customer_city_norm`，避免每次查询执行 `LOWER()`。
- 如果搜索条件可以改为前缀匹配，用 `customer_city_norm LIKE 'sao%'` 配合索引。
- 如果必须任意位置包含匹配，普通 BTree 不是合适结构，应评估 MySQL FULLTEXT、倒排索引或离线维表。

### 优化前 vs 优化后实测对比

本地 MySQL 8.0 使用 `EXPLAIN ANALYZE` 实测如下：

| 指标 | 原 SQL | 当前优化 SQL |
|------|--------|--------------|
| 总耗时 | `435 ms` | `1294 ms` |
| 最终输出行数 | 22 | 22 |
| `orders` 扫描 | 全表扫描 `99,441` 行，过滤后 `96,211` 行 | `orders` 被重复扫描多次，每次约 `99,441` 行 |
| 城市过滤 | 对 `96,211` 个订单逐次按 `customer_id` 查客户，再执行 `LOWER(customer_city) LIKE '%sao%'`，得到约 `20,367` 个订单 | 同样的客户城市过滤在多个 CTE 分支中重复执行 |
| 明细连接 | `order_items` 命中 `23,418` 行，`order_reviews` 命中 `23,568` 行 | `item_revenue_by_order` 物化约 `20,367` 行，`review_by_order` 物化约 `20,236` 行 |
| 聚合方式 | 在 join 后的 `23,568` 行上 `GROUP BY customer_state`，并做 `COUNT(DISTINCT)` | 先聚合订单收入和订单评价，再 hash join 回过滤订单 |
| 统计正确性 | `SUM(oi.price)` 可能被 review 行数放大 | revenue 和 avg_score 先回到订单粒度，避免一对多 join 乘法 |

原 SQL 的关键执行片段：

```text
-> Sort: revenue DESC (actual time=435..435 rows=22 loops=1)
    -> Group aggregate: count(distinct orders.order_id), sum(order_items.price), avg(order_reviews.review_score)
        -> Sort: c.customer_state (actual time=427..429 rows=23568 loops=1)
            -> Nested loop left join (actual time=0.0587..419 rows=23568 loops=1)
                -> Filter: order_status='delivered' and purchase >= '2017-01-01'
                    -> Table scan on orders (actual time=0.0136..19.1 rows=99441 loops=1)
                -> Index lookup on customers by customer_id, then LOWER(customer_city) LIKE '%sao%'
                -> Index lookup on order_items by order_id
                -> Index lookup on order_reviews by order_id
```

当前优化 SQL 的关键执行片段：

```text
-> Sort: revenue DESC (actual time=1294..1294 rows=22 loops=1)
    -> Aggregate using temporary table (actual time=1294..1294 rows=22 loops=1)
        -> Left hash join review_by_order (actual time=921..1288 rows=20367 loops=1)
            -> Left hash join item_revenue_by_order (actual time=373..678 rows=20367 loops=1)
                -> filtered orders + customers (actual time=0.0622..260 rows=20367 loops=1)
                -> Materialize CTE item_revenue_by_order (actual time=370..370 rows=20367 loops=1)
                -> Materialize CTE review_by_order (actual time=546..546 rows=20236 loops=1)
```

这次实测的结论是：**当前优化 SQL 修正了统计口径，但没有在本机数据量上变快**。主要原因是 MySQL 对 CTE/派生表的执行计划不理想，`filtered_orders` 相关逻辑被展开到 `item_revenue_by_order` 和 `review_by_order` 分支里重复计算，导致 `orders` 扫描、`customers` 城市过滤和临时表物化都重复发生。

如果目标是同时保证正确性和性能，我会继续做两点改进：

1. 把过滤后的订单先落到临时表，并给 `order_id` 加主键，避免多个 CTE 分支重复扫描 `orders/customers`：

```sql
CREATE TEMPORARY TABLE tmp_filtered_orders AS
SELECT
    o.order_id,
    c.customer_state
FROM orders AS o
INNER JOIN customers AS c
    ON o.customer_id = c.customer_id
WHERE o.order_status = 'delivered'
  AND o.order_purchase_timestamp >= '2017-01-01'
  AND LOWER(c.customer_city) LIKE '%sao%';

ALTER TABLE tmp_filtered_orders
    ADD PRIMARY KEY (order_id),
    ADD INDEX idx_tmp_customer_state (customer_state);
```

然后 `order_items` 和 `order_reviews` 都只 join `tmp_filtered_orders`。这样保留订单粒度预聚合，同时避免重复执行最贵的过滤逻辑。

2. 长期优化城市搜索字段。`LOWER(customer_city) LIKE '%sao%'` 是这条查询里最难通过普通索引优化的部分。如果业务经常做城市搜索，应新增标准化城市列，例如 `customer_city_norm`，并尽量把查询改为可索引的前缀匹配；如果必须任意位置匹配，则普通 BTree 不是合适方案，应考虑 FULLTEXT、倒排索引或离线城市维表。

---

## 第 3 问：潜在的统计错误（关键题）

> `SUM(oi.price)` 的结果可能不是你以为的「订单总收入」。为什么？

因为原 SQL 把 `order_items` 和 `order_reviews` 同时按 `order_id` JOIN 到订单上。

如果一个订单有 2 行商品、2 条评价，JOIN 后会得到 4 行：

```text
item_1 x review_1
item_1 x review_2
item_2 x review_1
item_2 x review_2
```

这时 `SUM(oi.price)` 会把每个商品金额按评价条数重复计算。`COUNT(DISTINCT o.order_id)` 只能修正订单数，不能修正 `SUM(oi.price)` 的重复累加。

另外，题目如果要的是平台 GMV，还需要明确是否包含 `freight_value`。Q2.2 的真实成交 GMV 口径应使用 `price + freight_value`。

**修正方案**：

```sql
WITH order_revenue AS (
    SELECT
        oi.order_id,
        SUM(oi.price) AS order_revenue
    FROM order_items AS oi
    GROUP BY
        oi.order_id
),
review_by_order AS (
    SELECT
        r.order_id,
        AVG(r.review_score) AS order_avg_score
    FROM order_reviews AS r
    GROUP BY
        r.order_id
)
SELECT
    c.customer_state,
    COUNT(*) AS orders,
    ROUND(SUM(COALESCE(orev.order_revenue, 0)), 2) AS revenue,
    ROUND(AVG(rbo.order_avg_score), 2) AS avg_score
FROM orders AS o
INNER JOIN customers AS c
    ON o.customer_id = c.customer_id
LEFT JOIN order_revenue AS orev
    ON o.order_id = orev.order_id
LEFT JOIN review_by_order AS rbo
    ON o.order_id = rbo.order_id
WHERE o.order_status = 'delivered'
  AND o.order_purchase_timestamp >= '2017-01-01'
  AND LOWER(c.customer_city) LIKE '%sao%'
GROUP BY
    c.customer_state
ORDER BY
    revenue DESC;
```
