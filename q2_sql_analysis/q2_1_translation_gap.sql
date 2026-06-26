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
--
-- 缺失翻译的业务处理方案
--
-- 方案一：人工补充翻译表
-- 优点：翻译准确，适合正式业务。
-- 缺点：需要人工维护。
--
-- 方案二：保留葡萄牙语类别名
-- 优点：不会丢失信息。
-- 缺点：英文用户阅读困难。
--
-- 方案三：统一标记为 Unknown / Untranslated
-- 优点：实现简单，方便统计。
-- 缺点：损失具体类别信息。
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