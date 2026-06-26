import pandas as pd

df = pd.read_csv("data/olist/olist_order_reviews_dataset.csv")

low = df[df["review_score"] <= 3].copy()

low["review_text"] = (
    low["review_comment_title"].fillna("").astype(str).str.strip()
    + " "
    + low["review_comment_message"].fillna("").astype(str).str.strip()
).str.strip()

print("低分评论数:", len(low))
print("有文本评论数:", (low["review_text"] != "").sum())
print("空文本评论数:", (low["review_text"] == "").sum())

print(low["review_text"].str.len().describe())
text_len = low.loc[low["review_text"] != "", "review_text"].str.len()

print(text_len.describe())
print(
    low[["review_id", "review_score", "review_text"]]
    .head(20)
    .to_string(index=False)
)
dup = (
    low[low["review_text"] != ""]
    .groupby("review_text")
    .size()
    .sort_values(ascending=False)
)

print("唯一评论：", len(dup))
print("重复评论：", (dup > 1).sum())

print(dup.head(30))