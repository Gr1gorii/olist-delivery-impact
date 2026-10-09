import numpy as np
import pandas as pd
import pytest
import statsmodels.formula.api as smf

from src.analysis import delay_features, financial_scenario, rating_model, scenario_inputs
from src.data import add_history
from src.diagnostics import repeat_purchases, review_diagnostics


def test_histories_require_earlier_purchase_and_observable_delivery():
    frame = pd.DataFrame({
        "seller_id": ["seller"] * 5,
        "customer_state": ["SP"] * 5,
        "category": ["books"] * 5,
        "order_purchase_timestamp": pd.to_datetime([
            "2018-01-01", "2018-01-05", "2018-01-05", "2018-01-06", "2018-01-10",
        ]),
        "order_delivered_customer_date": pd.to_datetime([
            "2018-01-05", "2018-01-07", "2018-01-05", "2018-01-03", "2018-01-12",
        ]),
        "late": [1, 0, 1, 1, 0],
    })
    result = add_history(frame)
    for group in ["seller", "region", "category"]:
        assert result[f"{group}_past_count"].tolist() == [0, 0, 0, 2, 3]
        assert result[f"{group}_past_late"].tolist() == pytest.approx([
            1 / 20, 1 / 20, 1 / 20, 3 / 22, 3 / 23,
        ])


def test_future_outcomes_do_not_change_checkout_history():
    frame = pd.DataFrame({
        "seller_id": ["one"] * 4,
        "customer_state": ["RJ"] * 4,
        "category": ["books"] * 4,
        "order_purchase_timestamp": pd.to_datetime([
            "2018-01-01", "2018-01-05", "2018-01-10", "2018-02-01",
        ]),
        "order_delivered_customer_date": pd.to_datetime([
            "2018-01-03", "2018-01-20", "2018-01-30", "2018-02-10",
        ]),
        "late": [1, 0, 0, 0],
    })
    original = add_history(frame)
    changed = frame.copy()
    changed.loc[1:, "late"] = 1
    changed = add_history(changed)
    for group in ["seller", "region", "category"]:
        pd.testing.assert_series_equal(
            original.loc[:2, f"{group}_past_late"],
            changed.loc[:2, f"{group}_past_late"],
        )


def test_repeat_margin_counts_each_unique_buyer_once():
    result = financial_scenario(
        3, 10, 2, 20, success=0.5, repeat_uplift=0.1,
        basket=100, margin=0.2, fix_cost=0,
        late_customer_counts=pd.Series([2, 1], index=["buyer_one", "buyer_two"]),
    )
    assert result["fixed_late"] == pytest.approx(1.5)
    assert result["fixed_customers"] == pytest.approx(0.75 + 0.5)
    assert result["repeat_margin"] == pytest.approx(1.25 * 0.1 * 100 * 0.2)


def test_repeat_margin_requires_unique_buyer_counts():
    with pytest.raises(ValueError):
        financial_scenario(3, 10, 2, 20, repeat_uplift=0.03)
    assert financial_scenario(3, 10, 2, 20)["repeat_margin"] == 0


def rating_sample():
    rng = np.random.default_rng(17)
    sample = pd.DataFrame({"seller_id": np.repeat([f"seller_{i}" for i in range(8)], 50)})
    seller_number = np.repeat(np.arange(8), 50)
    is_late = rng.random(len(sample)) < (0.2 + seller_number * 0.08)
    sample["delay_days"] = np.where(is_late, rng.integers(1, 31, len(sample)), -2)
    sample["late"] = is_late.astype(int)
    sample["seller_count"] = 1
    sample["log_price"] = rng.uniform(3, 6, len(sample))
    sample["freight"] = rng.uniform(5, 80, len(sample))
    sample["promised_days"] = rng.integers(5, 40, len(sample))
    sample["item_count"] = rng.integers(1, 4, len(sample))
    sample["customer_state"] = rng.choice(["SP", "RJ"], len(sample))
    sample["category"] = rng.choice(["books", "toys"], len(sample))
    sample["purchase_month"] = rng.integers(1, 4, len(sample))
    sample = delay_features(sample)
    sample["review_score"] = (
        3.5 + seller_number * 0.08 - 0.65 * sample["late"]
        - 0.03 * sample["day_1_7"] - 0.01 * sample["day_8_14"]
        - 0.004 * sample["day_15_30"] + 0.07 * sample["log_price"]
        - 0.05 * np.log1p(sample["freight"])
        + 0.08 * sample["customer_state"].eq("SP")
        + rng.normal(0, 0.02, len(sample))
    )
    return sample


def test_absorbed_seller_effects_match_explicit_dummy_regression():
    sample = rating_sample()
    sample["log_freight"] = np.log1p(sample["freight"])
    model, coefficients = rating_model(sample)
    explicit = smf.ols(
        "review_score ~ late + day_1_7 + day_8_14 + day_15_30"
        " + log_price + log_freight + promised_days + item_count"
        " + C(customer_state) + C(category) + C(purchase_month) + C(seller_id)",
        sample,
    ).fit()
    for term in ["late", "day_1_7", "day_8_14", "day_15_30"]:
        assert model["params"][term] == pytest.approx(explicit.params[term], abs=1e-8)
    assert coefficients["term"].tolist() == ["late", "day_1_7", "day_8_14", "day_15_30"]


def test_seller_rating_model_excludes_multi_seller_reviews():
    sample = rating_sample()
    ambiguous = sample.iloc[[0]].copy()
    ambiguous["seller_count"] = 2
    ambiguous["review_score"] = 999
    model, _ = rating_model(pd.concat([sample, ambiguous], ignore_index=True))
    assert len(model["sample"]) == len(sample)
    assert model["sample"]["seller_count"].eq(1).all()


def test_rating_scenario_gives_no_gain_for_unknown_or_ambiguous_seller():
    sample = rating_sample()
    model, _ = rating_model(sample)
    test = sample.iloc[:4].copy()
    test["late"] = 1
    test["delay_days"] = 3
    test.loc[test.index[1], "seller_id"] = "new_seller"
    test.loc[test.index[2], "seller_count"] = 2
    test.loc[test.index[3], "category"] = "new_category"
    result, unsupported = scenario_inputs(test, model, [], ["SP", "RJ"])
    assert unsupported == 3
    assert result["rating_gain"].iloc[0] > 0
    expected = -model["params"]["late"] - 3 * model["params"]["day_1_7"]
    assert result["rating_gain"].iloc[0] == pytest.approx(expected)
    assert result["rating_gain"].iloc[1:].eq(0).all()


def test_scenario_does_not_extrapolate_unestimable_delay_terms():
    sample = rating_sample()
    model, _ = rating_model(sample)
    model["params"] = model["params"].drop("day_15_30")
    model["columns"].remove("day_15_30")
    test = sample.iloc[[0]].copy()
    test["late"] = 1
    test["delay_days"] = 20
    result, unsupported = scenario_inputs(test, model, [], ["SP", "RJ"])
    assert unsupported == 1
    assert result["rating_gain"].iloc[0] == 0


def test_repeats_use_unique_customer_and_complete_followup(tmp_path):
    frame = pd.DataFrame({
        "order_id": ["first", "repeat", "single", "immature"],
        "customer_id": ["order_customer_a", "order_customer_b", "order_customer_c", "order_customer_d"],
        "customer_unique_id": ["buyer_a", "buyer_a", "buyer_b", "buyer_c"],
        "order_purchase_timestamp": pd.to_datetime(["2018-01-01", "2018-02-01", "2018-01-01", "2018-06-20"]),
        "order_delivered_customer_date": pd.to_datetime(["2018-01-05", "2018-02-05", "2018-01-05", "2018-06-25"]),
        "review_answer_timestamp": pd.to_datetime(["2018-01-06", "2018-02-06", "2018-01-06", "2018-06-26"]),
        "review_score": [2, 5, 5, 2],
        "late": [1, 0, 0, 1], "price": [100, 130, 80, 90],
    })
    summary = repeat_purchases(frame, observation_end="2018-07-01", horizon_days=90, reports=tmp_path)
    cohort = pd.read_csv(tmp_path / "repeat_cohort.csv")
    assert summary["identity"] == "customer_unique_id"
    assert summary["complete_followup_customers"] == 2
    assert summary["incomplete_followup_customers"] == 1
    assert summary["repeat_customers"] == 1
    repeat = cohort.loc[cohort["customer_unique_id"].eq("buyer_a")].iloc[0]
    assert repeat["first_repeat_order_id"] == "repeat"
    assert repeat["repeat_90d"] == 1
    assert "buyer_c" not in cohort["customer_unique_id"].tolist()


def test_survey_timing_and_text_coverage_use_explicit_denominators(tmp_path):
    frame = pd.DataFrame({
        "review_score": [5, 4, 1, np.nan], "late": [1] * 4,
        "review_comment_title": [None, " ", "Late parcel", None],
        "review_comment_message": [None, "", None, None],
        "order_delivered_customer_date": pd.to_datetime([
            "2018-04-10 12:00", "2018-04-10 12:00", "2018-04-11 12:00", "2018-04-12 12:00",
        ]),
        "review_creation_date": pd.to_datetime([
            "2018-04-10 00:00", "2018-04-10 12:00", "2018-04-10 00:00", None,
        ]),
        "review_answer_timestamp": pd.to_datetime([
            "2018-04-12 12:00", "2018-04-10 12:00", "2018-04-10 12:00", None,
        ]),
    })
    summary = review_diagnostics(frame, reports=tmp_path)
    timing = pd.read_csv(tmp_path / "review_timing.csv")
    scored = timing.loc[timing["population"].eq("reviewed_late") & timing["definition"].eq("timestamp")]
    assert scored.set_index("review_time")["before_delivery"].to_dict() == {"creation": 2, "answer": 1}
    assert scored["orders"].eq(3).all()
    all_late = timing.loc[timing["population"].eq("all_late") & timing["definition"].eq("timestamp")]
    assert all_late["orders"].eq(4).all()
    assert all_late["missing_review_time"].eq(1).all()
    assert summary["without_text_share"] == pytest.approx(2 / 3)
    assert summary["without_text_mean_score"] == pytest.approx(4.5)
    assert summary["with_text_mean_score"] == pytest.approx(1)
