-- ============================================================
-- Q2.1 商品类别英文翻译缺失分析
-- ============================================================
-- 目的：
-- 找出 products 表中没有对应英文翻译的商品类别。
--
-- 思路：
-- 1. 以 products 为主表。
-- 2. LEFT JOIN 翻译表。
-- 3. 找 translation 为 NULL 的类别。
-- 4. 显式统计 product_category_name 为 NULL 的商品。

-- ============================================================

USE olist;

SELECT
    COALESCE(
        p.product_category_name,
        'NULL'
    ) AS missing_category,
    COUNT(*) AS product_count
FROM products AS p
LEFT JOIN product_category_name_translation AS t
    ON p.product_category_name = t.product_category_name
WHERE
    p.product_category_name IS NULL
    OR t.product_category_name_english IS NULL
GROUP BY
    p.product_category_name
ORDER BY
    product_count DESC;