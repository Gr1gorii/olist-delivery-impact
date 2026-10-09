import numpy as np
import pandas as pd
from linearmodels.iv.absorbing import AbsorbingLS


def survey_gap(frame, time_column="review_creation_date", calendar_day=False, same_seller_day=False):
    sample = frame.loc[
        frame["late"].eq(1) & frame["seller_count"].eq(1)
        & frame["review_score"].notna() & frame[time_column].notna()
        & frame["order_delivered_customer_date"].notna() & frame["delay_days"].gt(0)
        & frame["seller_id"].notna() & frame["delay_days"].notna()
    ].copy()
    review_time = sample[time_column]
    delivery = sample["order_delivered_customer_date"]
    if calendar_day:
        review_time = review_time.dt.normalize()
        delivery = delivery.dt.normalize()
    sample["before_delivery"] = review_time.lt(delivery).astype(int)
    input_orders = len(sample)
    counts = sample.groupby("delay_days")["before_delivery"].nunique()
    shared_days = counts.loc[counts.eq(2)].index
    sample = sample.loc[sample["delay_days"].isin(shared_days)].copy()
    if same_seller_day:
        counts = sample.groupby(["seller_id", "delay_days"])["before_delivery"].nunique()
        shared_cells = counts.loc[counts.eq(2)].reset_index()[["seller_id", "delay_days"]]
        sample = sample.merge(shared_cells, on=["seller_id", "delay_days"], validate="many_to_one")
    if sample.empty or sample["before_delivery"].nunique() < 2:
        raise ValueError("No comparable before/after-delivery reviews at the same delay.")
    sample = sample.reset_index(drop=True)
    design = pd.DataFrame({"const": 1.0, "before_delivery": sample["before_delivery"].astype(float)})
    if same_seller_day:
        cell = sample["seller_id"].astype(str) + ":" + sample["delay_days"].astype(str)
        absorbed = pd.DataFrame({"seller_day": cell.astype("category")})
    else:
        absorbed = sample[["seller_id", "delay_days"]].astype("category")
    result = AbsorbingLS(sample["review_score"], design, absorb=absorbed).fit(
        cov_type="clustered", clusters=sample["seller_id"], debiased=True, method="hdfe",
    )
    interval = result.conf_int().loc["before_delivery"]
    means = sample.groupby("before_delivery")["review_score"].mean()
    return {
        "time_column": time_column, "calendar_day": calendar_day,
        "fixed_effects": "seller_by_delay_day" if same_seller_day else "seller_and_exact_delay_day",
        "input_orders": input_orders, "orders": len(sample),
        "excluded_no_overlap": input_orders - len(sample), "sellers": sample["seller_id"].nunique(),
        "before_orders": int(sample["before_delivery"].sum()),
        "after_orders": int(sample["before_delivery"].eq(0).sum()),
        "delay_days": sorted(sample["delay_days"].unique().astype(int).tolist()),
        "before_rating": float(means[1]), "after_rating": float(means[0]),
        "raw_gap": float(means[1] - means[0]),
        "coefficient": float(result.params["before_delivery"]),
        "low": float(interval.iloc[0]), "high": float(interval.iloc[1]),
        "standard_error": float(np.sqrt(result.cov.loc["before_delivery", "before_delivery"])),
        "interpretation": "Observational comparison of survey creation, not response timing." if time_column == "review_creation_date" else "Observational comparison of response timing.",
    }
