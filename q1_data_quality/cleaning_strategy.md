# Q1.3 清洗策略

本数据不适合统一 `dropna/drop_duplicates`，应按用途分层。销售报表以 **gross product sales** 为主：只保留数字 Invoice、产品 StockCode、`Quantity > 0`、`Price > 0`；**net product sales** 再把 `C` 取消/退货作为抵减。

RFM 只使用有 `Customer ID` 的商品销售和退货。缺失客户 ID 的 243,007 行不是随机空值，也不全是损耗：损耗行 100% 缺客户 ID，但只占缺失群体 1.42%，主体更像 anonymous/dotcom/system channel。

商品推荐/关联规则只用正向产品销售，把 invoice 当作购物篮，并按订单规模分层。唯一商品数中位数是 15，但 P99 为 196.85，最大 1,108；50+ 商品 invoice 占 10.43%，会放大共现。规则评价不能只看 confidence，还要看 lift、Kulczynski 和 imbalance。

看起来脏但不应直接删除的数据包括 `C` 取消单、`A` 坏账、Quantity 配对、缺失客户订单、零价损耗和重复行。删除缺失客户、所有负数量、零价行或精确重复行都是有损操作，只有指标明确不需要这些语义时才可做。
