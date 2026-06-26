-- ============================================================
-- Q2.3 卖家维度分析
-- ============================================================
-- 口径说明：
-- 1. 2017 年范围按 orders.order_purchase_timestamp 过滤。
-- 2. GMV 使用已送达订单的 price + freight_value，避免取消订单污染真实成交。
-- 3. 先聚合到 seller_id + order_id 粒度，避免同一订单多件商品放大订单数。
-- 4. order_reviews 先按 order_id 聚合，避免一单多评导致评分和金额重复。
-- 5. late_delivery_rate 的分母为可判断是否延迟的已送达订单。
-- 6. cancel_rate 的分母为该卖家 2017 年全部订单。
-- ============================================================

USE olist;

WITH review_by_order AS (
    SELECT
        r.order_id,
        AVG(r.review_score) AS order_review_score
    FROM order_reviews AS r
    GROUP BY
        r.order_id
),
seller_order_2017 AS (
    SELECT
        oi.seller_id,
        o.order_id,
        o.customer_id,
        o.order_status,
        o.order_delivered_customer_date,
        o.order_estimated_delivery_date,
        SUM(oi.price + oi.freight_value) AS seller_order_gmv
    FROM order_items AS oi
    INNER JOIN orders AS o
        ON oi.order_id = o.order_id
    WHERE o.order_purchase_timestamp >= '2017-01-01'
      AND o.order_purchase_timestamp < '2018-01-01'
    GROUP BY
        oi.seller_id,
        o.order_id,
        o.customer_id,
        o.order_status,
        o.order_delivered_customer_date,
        o.order_estimated_delivery_date
),
seller_metrics AS (
    SELECT
        so.seller_id,
        s.seller_state,
        ROUND(
            SUM(
                CASE
                    WHEN so.order_status = 'delivered' THEN so.seller_order_gmv
                    ELSE 0
                END
            ),
            2
        ) AS gmv_2017,
        COUNT(*) AS order_count,
        COUNT(DISTINCT so.customer_id) AS unique_customers,
        ROUND(AVG(rbo.order_review_score), 2) AS avg_review_score,
        ROUND(
            100 * SUM(
                CASE
                    WHEN so.order_status = 'delivered'
                         AND so.order_delivered_customer_date IS NOT NULL
                         AND so.order_estimated_delivery_date IS NOT NULL
                         AND so.order_delivered_customer_date > so.order_estimated_delivery_date
                    THEN 1
                    ELSE 0
                END
            ) / NULLIF(
                SUM(
                    CASE
                        WHEN so.order_status = 'delivered'
                             AND so.order_delivered_customer_date IS NOT NULL
                             AND so.order_estimated_delivery_date IS NOT NULL
                        THEN 1
                        ELSE 0
                    END
                ),
                0
            ),
            2
        ) AS late_delivery_rate,
        ROUND(
            100 * SUM(CASE WHEN so.order_status = 'canceled' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0),
            2
        ) AS cancel_rate
    FROM seller_order_2017 AS so
    INNER JOIN sellers AS s
        ON so.seller_id = s.seller_id
    LEFT JOIN review_by_order AS rbo
        ON so.order_id = rbo.order_id
    GROUP BY
        so.seller_id,
        s.seller_state
),
ranked_sellers AS (
    SELECT
        seller_id,
        seller_state,
        gmv_2017,
        order_count,
        unique_customers,
        avg_review_score,
        late_delivery_rate,
        cancel_rate,
        RANK() OVER (
            PARTITION BY seller_state
            ORDER BY gmv_2017 DESC
        ) AS state_rank
    FROM seller_metrics
)
SELECT
    seller_id,
    seller_state,
    gmv_2017,
    order_count,
    unique_customers,
    avg_review_score,
    late_delivery_rate,
    cancel_rate,
    state_rank
FROM ranked_sellers
ORDER BY
    gmv_2017 DESC,
    seller_id
LIMIT 20;
