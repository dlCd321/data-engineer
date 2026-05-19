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

（候选人请填写）

### 问题 2：

（候选人请填写）

### 问题 3：

（候选人请填写）

---

## 第 2 问：优化方案

### 优化后的 SQL

```sql
-- TODO
```

### 建议添加的索引

```sql
-- TODO
```

### 优化前 vs 优化后实测对比

| 指标 | 优化前 | 优化后 |
|------|--------|--------|
| 执行时间 | | |
| 扫描行数 | | |

---

## 第 3 问：潜在的统计错误（关键题）

> `SUM(oi.price)` 的结果可能不是你以为的「订单总收入」。为什么？

（候选人请填写）

**修正方案**：

```sql
-- TODO
```
