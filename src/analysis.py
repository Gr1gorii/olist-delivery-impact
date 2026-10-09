import numpy as np
import pandas as pd
from linearmodels.iv.absorbing import AbsorbingLS


def delay_features(frame):
    frame = frame.copy()
    delay = frame["delay_days"].clip(lower=0)
    frame["day_1_7"] = delay.clip(upper=7)
    frame["day_8_14"] = (delay - 7).clip(lower=0, upper=7)
    frame["day_15_30"] = (delay - 14).clip(lower=0, upper=16)
    return frame


def rating_design(frame, levels):
    numeric = ["late", "day_1_7", "day_8_14", "day_15_30", "log_price", "promised_days", "item_count"]
    design = frame[numeric].astype(float).copy()
    design["log_freight"] = np.log1p(frame["freight"])
    design.insert(0, "const", 1.0)
    for column, values in levels.items():
        categories = pd.Series(pd.Categorical(frame[column], categories=values), index=frame.index)
        dummies = pd.get_dummies(categories, prefix=column, drop_first=True, dtype=float)
        design = pd.concat([design, dummies], axis=1)
    return design


def rating_model(frame):
    sample = frame.loc[frame["seller_count"].eq(1)].dropna(subset=["review_score", "seller_id"]).copy()
    sample = delay_features(sample).reset_index(drop=True)
    levels = {column: sorted(sample[column].unique().tolist()) for column in ["customer_state", "category", "purchase_month"]}
    design = rating_design(sample, levels)
    absorbed = sample[["seller_id"]].astype("category")
    result = AbsorbingLS(sample["review_score"], design, absorb=absorbed, drop_absorbed=True).fit(
        cov_type="clustered", clusters=sample["seller_id"], debiased=True, method="hdfe",
    )
    params = result.params
    effects = sample["review_score"] - design[params.index].dot(params) - result.resids
    model = {
        "result": result, "params": params, "columns": params.index.tolist(), "levels": levels,
        "seller_effect": effects.groupby(sample["seller_id"]).mean(),
        "known_categories": set(sample["category"]), "known_states": set(sample["customer_state"]),
        "known_sellers": set(sample["seller_id"]), "sample": sample,
    }
    terms = ["late", "day_1_7", "day_8_14", "day_15_30"]
    interval = result.conf_int().reindex(terms)
    coefficients = pd.DataFrame({
        "term": terms, "coefficient": params.reindex(terms).values,
        "low": interval.iloc[:, 0].values, "high": interval.iloc[:, 1].values,
    })
    return model, coefficients


def predict_rating(frame, model):
    design = rating_design(delay_features(frame), model["levels"])
    return design[model["columns"]].dot(model["params"]) + frame["seller_id"].map(model["seller_effect"])


def rating_comparison(model, name):
    sample = model["sample"]
    result = model["result"]
    means = sample.groupby("late")["review_score"].mean()
    terms = ["late", "day_1_7"]
    first_day = result.params.loc[terms].sum()
    first_error = np.sqrt(result.cov.loc[terms, terms].to_numpy().sum())
    return {
        "sample": name, "reviews": len(sample), "sellers": sample["seller_id"].nunique(),
        "on_time_rating": means.get(0, np.nan), "late_rating": means.get(1, np.nan),
        "raw_difference": means.get(1, np.nan) - means.get(0, np.nan),
        "threshold": result.params["late"], "first_day": first_day,
        "first_day_low": first_day - 1.96 * first_error, "first_day_high": first_day + 1.96 * first_error,
        "day_1_7": result.params["day_1_7"], "r_squared": result.rsquared,
    }


def priorities(refit, test, key, limit, minimum):
    old = refit.groupby(key).agg(orders=("late", "size"), late_orders=("late", "sum"))
    selected = old.loc[old["orders"].ge(minimum)].sort_values(["late_orders", "orders"], ascending=False).head(limit).index.tolist()
    current = test.groupby(key).agg(
        orders=("late", "size"), late_orders=("late", "sum"),
        rating=("review_score", "mean"), median_delay=("delay_days", "median"),
    )
    current["late_rate"] = current["late_orders"] / current["orders"]
    current["late_share"] = current["late_orders"] / test["late"].sum()
    current["selected_before_test"] = current.index.isin(selected)
    current["previous_orders"] = old["orders"]
    current["previous_late_orders"] = old["late_orders"]
    return current.reset_index().sort_values("late_orders", ascending=False), selected


def scenario_inputs(test, model, sellers, regions):
    test = delay_features(test)
    supported = (
        test["seller_count"].eq(1) & test["category"].isin(model["known_categories"])
        & test["customer_state"].isin(model["known_states"]) & test["seller_id"].isin(model["known_sellers"])
    )
    for term in ["late", "day_1_7", "day_8_14", "day_15_30"]:
        if term not in model["params"]:
            supported &= test[term].eq(0)
    test["rating_gain"] = 0.0
    subset = test.loc[supported].copy()
    fixed = subset.copy()
    fixed["delay_days"] = 0
    fixed[["late", "day_1_7", "day_8_14", "day_15_30"]] = 0
    predicted = predict_rating(subset, model).clip(1, 5)
    corrected = predict_rating(fixed, model).clip(1, 5)
    test.loc[supported, "rating_gain"] = (corrected - predicted).clip(lower=0)
    test["targeted"] = (test["seller_id"].isin(sellers) & test["seller_count"].eq(1)) | test["customer_state"].isin(regions)
    return test, int((~supported).sum())


def financial_scenario(target_late, affected_orders, gain_sum, all_reviews, success=0.5, contact_rate=0.5, contact_cost=8.0, compensation_rate=0.2, compensation=20.0, repeat_uplift=0.0, basket=140.0, margin=0.15, fix_cost=3.0, late_customer_counts=None):
    if repeat_uplift > 0 and late_customer_counts is None:
        raise ValueError("Repeat benefits require late-order counts grouped by customer_unique_id.")
    fixed = target_late * success
    fixed_customers = sum(1 - (1 - success) ** count for count in late_customer_counts) if late_customer_counts is not None else 0.0
    support = fixed * contact_rate * contact_cost
    refunds = fixed * compensation_rate * compensation
    repeat = fixed_customers * repeat_uplift * basket * margin
    implementation = affected_orders * fix_cost
    return {
        "target_late": int(target_late), "affected_orders": int(affected_orders),
        "success": success, "fixed_late": fixed, "fixed_customers": fixed_customers,
        "repeat_uplift": repeat_uplift, "support": support,
        "compensation": refunds, "repeat_margin": repeat, "implementation": implementation,
        "net": support + refunds + repeat - implementation,
        "rating_uplift": gain_sum * success / max(all_reviews, 1),
        "break_even_cost": (support + refunds + repeat) / max(affected_orders, 1),
    }
