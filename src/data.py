from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
REPORTS = ROOT / "reports"


def calendar_delay(delivered, promised):
    return (delivered.dt.normalize() - promised.dt.normalize()).dt.days


def first_reviews(reviews):
    reviews = reviews.sort_values(["review_answer_timestamp", "review_id"])
    return reviews.drop_duplicates("order_id", keep="first")


def load_orders(raw=RAW):
    tables = {}
    for name in ["orders", "order_items", "order_reviews", "customers", "products", "sellers"]:
        tables[name] = pd.read_csv(raw / f"olist_{name}_dataset.csv")
    orders = tables["orders"]
    reviews = tables["order_reviews"]
    for column in orders.columns:
        if column.endswith("date") or column.endswith("timestamp") or column == "order_approved_at":
            orders[column] = pd.to_datetime(orders[column])
    for column in ["review_creation_date", "review_answer_timestamp"]:
        reviews[column] = pd.to_datetime(reviews[column])

    items = tables["order_items"].merge(tables["products"], on="product_id", validate="many_to_one")
    items = items.merge(tables["sellers"], on="seller_id", validate="many_to_one")
    totals = items.groupby("order_id").agg(
        price=("price", "sum"), freight=("freight_value", "sum"),
        item_count=("order_item_id", "count"), seller_count=("seller_id", "nunique"),
        weight=("product_weight_g", "sum"),
    ).reset_index()
    seller_value = items.groupby(["order_id", "seller_id"])["price"].sum().reset_index()
    primary = seller_value.sort_values(["price", "seller_id"], ascending=[False, True])
    primary = primary.drop_duplicates("order_id")[["order_id", "seller_id"]]
    primary = primary.merge(tables["sellers"][["seller_id", "seller_state"]], on="seller_id", validate="many_to_one")
    category = items.sort_values(["price", "product_id"], ascending=[False, True])
    category = category.drop_duplicates("order_id")[["order_id", "product_category_name"]]

    orders = orders.merge(totals, on="order_id", how="left", validate="one_to_one")
    orders = orders.merge(primary, on="order_id", how="left", validate="one_to_one")
    orders = orders.merge(category, on="order_id", how="left", validate="one_to_one")
    orders = orders.merge(tables["customers"][["customer_id", "customer_unique_id", "customer_state"]], on="customer_id", validate="one_to_one")
    orders = orders.merge(first_reviews(reviews), on="order_id", how="left", validate="one_to_one")
    orders = orders.rename(columns={"product_category_name": "category"})
    orders["delay_days"] = calendar_delay(orders["order_delivered_customer_date"], orders["order_estimated_delivery_date"])
    orders["late"] = orders["delay_days"].gt(0).astype(int)
    orders["promised_days"] = calendar_delay(orders["order_estimated_delivery_date"], orders["order_purchase_timestamp"])
    orders["purchase_month"] = orders["order_purchase_timestamp"].dt.month
    orders["purchase_weekday"] = orders["order_purchase_timestamp"].dt.dayofweek
    orders["purchase_hour"] = orders["order_purchase_timestamp"].dt.hour
    orders["same_state"] = orders["seller_state"].eq(orders["customer_state"]).astype(int)
    orders["log_price"] = np.log1p(orders["price"])
    orders["freight_share"] = orders["freight"] / orders["price"].clip(lower=1)
    orders["category"] = orders["category"].fillna("unknown")
    text = orders["review_comment_title"].fillna("").str.strip() + orders["review_comment_message"].fillna("").str.strip()
    orders["has_text"] = text.str.len().gt(0)
    orders["survey_before_delivery"] = orders["review_creation_date"].lt(orders["order_delivered_customer_date"])
    orders["response_before_delivery"] = orders["review_answer_timestamp"].lt(orders["order_delivered_customer_date"])
    quality = {
        "raw_orders": len(orders), "raw_reviews": len(reviews),
        "extra_reviews": len(reviews) - reviews["order_id"].nunique(),
        "without_items": int(orders["item_count"].isna().sum()),
        "without_score": int(orders["review_score"].isna().sum()),
        "statuses": orders["order_status"].value_counts().to_dict(),
    }
    valid = (
        orders["order_status"].eq("delivered")
        & orders["delay_days"].notna() & orders["item_count"].notna()
        & orders["order_delivered_customer_date"].ge(orders["order_purchase_timestamp"])
        & orders["promised_days"].ge(0)
    )
    frame = orders.loc[valid].sort_values("order_purchase_timestamp").reset_index(drop=True)
    quality["eligible_delivered"] = len(frame)
    quality["excluded"] = len(orders) - len(frame)
    quality["multi_seller"] = int(frame["seller_count"].gt(1).sum())
    quality["reviews_before_delivery"] = int(frame["review_answer_timestamp"].lt(frame["order_delivered_customer_date"]).sum())
    quality["purchase_min"] = str(frame["order_purchase_timestamp"].min())
    quality["purchase_max"] = str(frame["order_purchase_timestamp"].max())
    return frame, quality


def add_history(frame):
    frame = frame.copy()
    for key, prefix in [("seller_id", "seller"), ("customer_state", "region"), ("category", "category")]:
        frame[f"{prefix}_past_count"] = 0.0
        frame[f"{prefix}_past_late"] = 0.05
        for _, group in frame.groupby(key):
            events = group.loc[group["order_delivered_customer_date"].ge(group["order_purchase_timestamp"])].sort_values("order_delivered_customer_date")
            times = events["order_delivered_customer_date"].to_numpy()
            purchases = group["order_purchase_timestamp"].to_numpy()
            counts = np.searchsorted(times, purchases, side="left")
            late_count = np.r_[0, events["late"].to_numpy().cumsum()][counts]
            frame.loc[group.index, f"{prefix}_past_count"] = counts
            frame.loc[group.index, f"{prefix}_past_late"] = (late_count + 1) / (counts + 20)
    return frame


def time_split(frame):
    purchase = frame["order_purchase_timestamp"]
    delivery = frame["order_delivered_customer_date"]
    train = frame.loc[purchase.lt("2018-01-01") & delivery.lt("2018-01-01")]
    valid = frame.loc[purchase.ge("2018-01-01") & purchase.lt("2018-04-01") & delivery.lt("2018-04-01")]
    test = frame.loc[purchase.ge("2018-04-01") & purchase.lt("2018-08-01") & delivery.lt("2018-09-01")]
    test = test.copy()
    test.loc[test["review_answer_timestamp"].ge("2018-09-01"), "review_score"] = np.nan
    return train.copy(), valid.copy(), test
