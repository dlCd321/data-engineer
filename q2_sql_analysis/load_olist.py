import os
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.types import DateTime, Float, Integer, Numeric, String, Text

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.getenv("OLIST_DATA_DIR", ROOT_DIR / "data" / "olist")).resolve()

MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "olist")
MYSQL_CHARSET = "utf8mb4"
CHUNKSIZE = int(os.getenv("OLIST_LOAD_CHUNKSIZE", "5000"))


FILES = {
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "order_reviews": "olist_order_reviews_dataset.csv",
    "products": "olist_products_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "order_payments": "olist_order_payments_dataset.csv",
    "geolocation": "olist_geolocation_dataset.csv",
    "product_category_name_translation": "product_category_name_translation.csv",
}

READ_OPTIONS = {
    "orders": {
        "parse_dates": [
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ],
    },
    "order_items": {"parse_dates": ["shipping_limit_date"]},
    "order_reviews": {
        "parse_dates": ["review_creation_date", "review_answer_timestamp"],
    },
}

COMMON_STRING_COLUMNS = {
    "order_id": "string",
    "customer_id": "string",
    "customer_unique_id": "string",
    "product_id": "string",
    "seller_id": "string",
    "review_id": "string",
    "order_status": "string",
    "payment_type": "string",
    "customer_zip_code_prefix": "string",
    "seller_zip_code_prefix": "string",
    "geolocation_zip_code_prefix": "string",
    "customer_city": "string",
    "customer_state": "string",
    "seller_city": "string",
    "seller_state": "string",
    "geolocation_city": "string",
    "geolocation_state": "string",
    "product_category_name": "string",
    "product_category_name_english": "string",
}

TABLE_DTYPES = {
    "orders": {
        "order_id": String(64),
        "customer_id": String(64),
        "order_status": String(32),
        "order_purchase_timestamp": DateTime(),
        "order_approved_at": DateTime(),
        "order_delivered_carrier_date": DateTime(),
        "order_delivered_customer_date": DateTime(),
        "order_estimated_delivery_date": DateTime(),
    },
    "order_items": {
        "order_id": String(64),
        "order_item_id": Integer(),
        "product_id": String(64),
        "seller_id": String(64),
        "shipping_limit_date": DateTime(),
        "price": Numeric(12, 2),
        "freight_value": Numeric(12, 2),
    },
    "order_reviews": {
        "review_id": String(64),
        "order_id": String(64),
        "review_score": Integer(),
        "review_comment_title": Text(),
        "review_comment_message": Text(),
        "review_creation_date": DateTime(),
        "review_answer_timestamp": DateTime(),
    },
    "products": {
        "product_id": String(64),
        "product_category_name": String(128),
        "product_name_lenght": Integer(),
        "product_description_lenght": Integer(),
        "product_photos_qty": Integer(),
        "product_weight_g": Integer(),
        "product_length_cm": Integer(),
        "product_height_cm": Integer(),
        "product_width_cm": Integer(),
    },
    "customers": {
        "customer_id": String(64),
        "customer_unique_id": String(64),
        "customer_zip_code_prefix": String(16),
        "customer_city": String(128),
        "customer_state": String(8),
    },
    "sellers": {
        "seller_id": String(64),
        "seller_zip_code_prefix": String(16),
        "seller_city": String(128),
        "seller_state": String(8),
    },
    "order_payments": {
        "order_id": String(64),
        "payment_sequential": Integer(),
        "payment_type": String(32),
        "payment_installments": Integer(),
        "payment_value": Numeric(12, 2),
    },
    "geolocation": {
        "geolocation_zip_code_prefix": String(16),
        "geolocation_lat": Float(),
        "geolocation_lng": Float(),
        "geolocation_city": String(128),
        "geolocation_state": String(8),
    },
    "product_category_name_translation": {
        "product_category_name": String(128),
        "product_category_name_english": String(128),
    },
}


INDEX_SQL = [
    "CREATE INDEX idx_orders_order_id ON orders(order_id)",
    "CREATE INDEX idx_orders_customer_id ON orders(customer_id)",
    "CREATE INDEX idx_orders_status_purchase ON orders(order_status, order_purchase_timestamp, order_id)",
    "CREATE INDEX idx_order_items_order_id ON order_items(order_id)",
    "CREATE INDEX idx_order_items_seller_order ON order_items(seller_id, order_id)",
    "CREATE INDEX idx_reviews_order_id ON order_reviews(order_id)",
    "CREATE INDEX idx_products_product_id ON products(product_id)",
    "CREATE INDEX idx_products_category ON products(product_category_name)",
    "CREATE INDEX idx_customers_customer_id ON customers(customer_id)",
    "CREATE INDEX idx_customers_city_id_state ON customers(customer_city, customer_id, customer_state)",
    "CREATE INDEX idx_sellers_seller_id ON sellers(seller_id)",
]


def build_url(database: str | None = None) -> URL:
    return URL.create(
        "mysql+pymysql",
        username=MYSQL_USER,
        password=MYSQL_PASSWORD,
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        database=database,
        query={"charset": MYSQL_CHARSET},
    )


def ensure_database() -> None:
    engine = create_engine(build_url())
    with engine.begin() as conn:
        conn.execute(
            text(
                f"CREATE DATABASE IF NOT EXISTS `{MYSQL_DATABASE}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
            )
        )
    engine.dispose()


def read_csv(table_name: str, file_name: str) -> pd.DataFrame:
    path = DATA_DIR / file_name
    if not path.exists():
        raise FileNotFoundError(f"找不到数据文件：{path}")

    dtype = {
        column: dtype
        for column, dtype in COMMON_STRING_COLUMNS.items()
        if column in TABLE_DTYPES[table_name]
    }
    options = READ_OPTIONS.get(table_name, {})
    return pd.read_csv(path, encoding="utf-8-sig", dtype=dtype, **options)


def load_tables() -> None:
    ensure_database()
    engine = create_engine(build_url(MYSQL_DATABASE))

    try:
        for table_name, file_name in FILES.items():
            print(f"[LOAD] {file_name} -> {MYSQL_DATABASE}.{table_name}")
            df = read_csv(table_name, file_name)
            df.to_sql(
                table_name,
                con=engine,
                if_exists="replace",
                index=False,
                chunksize=CHUNKSIZE,
                method="multi",
                dtype=TABLE_DTYPES[table_name],
            )
            print(f"[OK] {table_name}: {len(df):,} rows")

        print("[INDEX] Creating query indexes")
        with engine.begin() as conn:
            for sql in INDEX_SQL:
                conn.execute(text(sql))
                print(f"[OK] {sql}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    load_tables()
