-- ============================================================
-- Q2.2 平台真实成交分析
-- ============================================================
-- 口径说明：
-- 1. 月份基于 orders.order_purchase_timestamp。
-- 2. delivered_gmv 只统计已送达订单，金额包含 price + freight_value。
-- 3. 先把 order_items 聚合到订单粒度，再连接 orders，避免订单数被明细行放大。
-- 4. avg_delivery_days 只统计 delivered 且实际送达时间非空的订单。
-- 5. cancel_rate 输出为百分比，保留 2 位小数。
-- ============================================================

USE olist;

WITH order_gmv AS (
    SELECT
        oi.order_id,
        SUM(oi.price + oi.freight_value) AS order_gmv
    FROM order_items AS oi
    GROUP BY
        oi.order_id
),
order_metrics AS (
    SELECT
        o.order_id,
        DATE_FORMAT(o.order_purchase_timestamp, '%Y-%m') AS month,
        o.order_status,
        o.order_purchase_timestamp,
        o.order_delivered_customer_date,
        COALESCE(g.order_gmv, 0) AS order_gmv
    FROM orders AS o
    LEFT JOIN order_gmv AS g
        ON o.order_id = g.order_id
)
SELECT
    month,
    COUNT(*) AS total_orders,
    SUM(CASE WHEN order_status = 'delivered' THEN 1 ELSE 0 END) AS delivered_orders,
    SUM(CASE WHEN order_status = 'canceled' THEN 1 ELSE 0 END) AS canceled_orders,
    ROUND(
        100 * SUM(CASE WHEN order_status = 'canceled' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0),
        2
    ) AS cancel_rate,
    ROUND(
        SUM(CASE WHEN order_status = 'delivered' THEN order_gmv ELSE 0 END),
        2
    ) AS delivered_gmv,
    ROUND(
        AVG(
            CASE
                WHEN order_status = 'delivered'
                     AND order_delivered_customer_date IS NOT NULL
                THEN TIMESTAMPDIFF(SECOND, order_purchase_timestamp, order_delivered_customer_date) / 86400
            END
        ),
        2
    ) AS avg_delivery_days
FROM order_metrics
GROUP BY
    month
ORDER BY
    month;
