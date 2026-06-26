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

| 指标 | 优化前 | 优化后 |
|------|--------|--------|
| 执行时间 | 本机 MySQL 服务未启动，未实测 | 本机 MySQL 服务未启动，未实测 |
| 扫描行数 | 建议用 `EXPLAIN ANALYZE` 记录 | 建议用 `EXPLAIN ANALYZE` 记录 |

本题当前先给出逻辑优化方案。实际提交前如果能启动 MySQL 8.0，可分别执行：

```sql
EXPLAIN ANALYZE
SELECT ...
```

对比重点不是只看总耗时，还要看 `orders`、`customers`、`order_items`、`order_reviews` 的实际扫描行数，以及是否出现大规模临时表/filesort。

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
