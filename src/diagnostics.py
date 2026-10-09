import numpy as np
import pandas as pd

from src.data import REPORTS


def review_diagnostics(frame, reports=REPORTS):
    reports.mkdir(parents=True, exist_ok=True)
    reviewed = frame.loc[frame["review_score"].notna()].copy()
    title = reviewed["review_comment_title"].fillna("").str.strip()
    message = reviewed["review_comment_message"].fillna("").str.strip()
    reviewed["has_text"] = title.ne("") | message.ne("")
    groups = pd.MultiIndex.from_product([[False, True], range(1, 6)], names=["has_text", "review_score"])
    scores = reviewed.groupby(["has_text", "review_score"]).size().reindex(groups, fill_value=0)
    scores = scores.rename("reviews").reset_index()
    scores["share"] = scores["reviews"] / scores.groupby("has_text")["reviews"].transform("sum").replace(0, np.nan)
    scores.to_csv(reports / "score_by_text.csv", index=False)
    coverage = reviewed.groupby("has_text").agg(
        reviews=("review_score", "size"), mean_score=("review_score", "mean"),
        low_score_reviews=("review_score", lambda values: values.le(2).sum()),
    ).reindex([False, True], fill_value=0).reset_index()
    coverage["share"] = coverage["reviews"] / max(len(reviewed), 1)
    coverage["low_score_share"] = coverage["low_score_reviews"] / coverage["reviews"].replace(0, np.nan)
    coverage.to_csv(reports / "text_coverage.csv", index=False)
    rows = []
    populations = {
        "all_late": frame.loc[frame["late"].eq(1)],
        "reviewed_late": reviewed.loc[reviewed["late"].eq(1)],
        "all_reviewed": reviewed,
    }
    for population, sample in populations.items():
        delivery = sample["order_delivered_customer_date"]
        for source, column in [("creation", "review_creation_date"), ("answer", "review_answer_timestamp")]:
            timestamp = sample[column]
            for definition in ["timestamp", "calendar_day"]:
                before = timestamp.lt(delivery) if definition == "timestamp" else timestamp.dt.normalize().lt(delivery.dt.normalize())
                rows.append({
                    "population": population, "review_time": source, "definition": definition,
                    "before_delivery": int(before.sum()), "orders": len(sample),
                    "share": float(before.sum() / len(sample)) if len(sample) else None,
                    "missing_review_time": int(timestamp.isna().sum()),
                    "missing_delivery_time": int(delivery.isna().sum()),
                })
    pd.DataFrame(rows).to_csv(reports / "review_timing.csv", index=False)
    no_text = reviewed.loc[~reviewed["has_text"]]
    with_text = reviewed.loc[reviewed["has_text"]]
    return {
        "scored_reviews": len(reviewed), "missing_scores": int(frame["review_score"].isna().sum()),
        "without_text": len(no_text), "with_text": len(with_text),
        "without_text_share": len(no_text) / max(len(reviewed), 1),
        "without_text_mean_score": float(no_text["review_score"].mean()) if len(no_text) else None,
        "with_text_mean_score": float(with_text["review_score"].mean()) if len(with_text) else None,
        "timing": rows,
    }


def repeat_purchases(frame, observation_end="2018-09-01", horizon_days=90, reports=REPORTS):
    reports.mkdir(parents=True, exist_ok=True)
    end = pd.Timestamp(observation_end)
    horizon = pd.Timedelta(days=horizon_days)
    if horizon_days <= 0:
        raise ValueError("horizon_days must be positive")
    orders = frame.loc[frame["customer_unique_id"].notna()].copy()
    orders = orders.sort_values(["order_purchase_timestamp", "order_id"])
    reviewed = orders.loc[orders["review_score"].notna()]
    first = reviewed.drop_duplicates("customer_unique_id").copy()
    first["anchor"] = first[["order_delivered_customer_date", "review_answer_timestamp"]].max(axis=1)
    first["followup_end"] = first["anchor"] + horizon
    known_review = first["review_answer_timestamp"].notna()
    complete = known_review & first["followup_end"].le(end)
    cohort = first.loc[complete].copy()
    history = orders.loc[orders["order_purchase_timestamp"].lt(end)]
    customer_orders = {customer: group.reset_index(drop=True) for customer, group in history.groupby("customer_unique_id")}
    rows = []
    for index in cohort.itertuples():
        group = customer_orders[index.customer_unique_id]
        times = group["order_purchase_timestamp"].to_numpy()
        anchor = np.datetime64(index.anchor, "ns")
        purchase = np.datetime64(index.order_purchase_timestamp, "ns")
        stop = np.datetime64(index.followup_end, "ns")
        start_position = np.searchsorted(times, anchor, side="right")
        end_position = np.searchsorted(times, stop, side="right")
        repeat = end_position > start_position
        first_repeat = group.iloc[start_position] if repeat else None
        pre_anchor_count = start_position - np.searchsorted(times, purchase, side="right")
        rows.append({
            "customer_unique_id": index.customer_unique_id, "customer_id": index.customer_id,
            "index_order_id": index.order_id, "index_purchase": index.order_purchase_timestamp,
            "late": int(index.late), "index_score": float(index.review_score),
            "anchor": index.anchor, "followup_end": index.followup_end,
            "repeat_90d": int(repeat), "repeat_orders": int(end_position - start_position),
            "pre_anchor_repeat_orders": int(pre_anchor_count),
            "first_repeat_order_id": first_repeat["order_id"] if repeat else None,
            "first_repeat_purchase": first_repeat["order_purchase_timestamp"] if repeat else None,
            "first_repeat_basket": float(first_repeat["price"]) if repeat else None,
        })
    columns = [
        "customer_unique_id", "customer_id", "index_order_id", "index_purchase", "late", "index_score",
        "anchor", "followup_end", "repeat_90d", "repeat_orders", "pre_anchor_repeat_orders",
        "first_repeat_order_id", "first_repeat_purchase", "first_repeat_basket",
    ]
    result = pd.DataFrame(rows, columns=columns)
    result.to_csv(reports / "repeat_cohort.csv", index=False)
    by_lateness = result.groupby("late").agg(
        customers=("customer_unique_id", "size"), repeat_customers=("repeat_90d", "sum"),
        repeat_rate=("repeat_90d", "mean"), mean_index_score=("index_score", "mean"),
    ).reindex([0, 1]).reset_index()
    by_lateness.to_csv(reports / "repeats_by_lateness.csv", index=False)
    counts = orders.groupby("customer_unique_id").size()
    on_time_rate = by_lateness.loc[by_lateness["late"].eq(0), "repeat_rate"].iloc[0]
    late_rate = by_lateness.loc[by_lateness["late"].eq(1), "repeat_rate"].iloc[0]
    gap = on_time_rate - late_rate
    baskets = result["first_repeat_basket"].dropna()
    return {
        "observation_end_exclusive": str(end), "horizon_days": horizon_days,
        "identity": "customer_unique_id", "eligible_orders": len(orders),
        "unique_customers": len(counts), "customers_with_multiple_orders": int(counts.gt(1).sum()),
        "first_reviewed_customers": len(first), "complete_followup_customers": len(result),
        "incomplete_followup_customers": int((known_review & ~complete).sum()),
        "missing_review_answer_customers": int((~known_review).sum()),
        "missing_customer_unique_id_orders": int(frame["customer_unique_id"].isna().sum()),
        "repeat_customers": int(result["repeat_90d"].sum()),
        "repeat_rate": float(result["repeat_90d"].mean()) if len(result) else None,
        "on_time_repeat_rate": float(on_time_rate) if pd.notna(on_time_rate) else None,
        "late_repeat_rate": float(late_rate) if pd.notna(late_rate) else None,
        "descriptive_repeat_rate_gap": float(gap) if pd.notna(gap) else None,
        "customers_with_excluded_pre_anchor_repeats": int(result["pre_anchor_repeat_orders"].gt(0).sum()),
        "excluded_pre_anchor_repeat_orders": int(result["pre_anchor_repeat_orders"].sum()),
        "observed_first_repeat_basket": float(baskets.mean()) if len(baskets) else None,
        "first_repeat_basket_observations": len(baskets),
        "interpretation": "Descriptive association in ultimately delivered orders; not a causal effect.",
    }
