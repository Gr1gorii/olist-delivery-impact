import numpy as np
import pandas as pd
import pytest

from src.analysis import financial_scenario
from src.data import add_history, calendar_delay, first_reviews, load_orders, time_split
from src.risk import FEATURES


def test_delivery_on_promised_evening_is_on_time():
    delivered = pd.Series(pd.to_datetime(["2018-04-10 23:59", "2018-04-11 00:01"]))
    promised = pd.Series(pd.to_datetime(["2018-04-10", "2018-04-10"]))
    assert calendar_delay(delivered, promised).tolist() == [0, 1]


def test_initial_review_does_not_get_replaced():
    reviews = pd.DataFrame({"order_id": ["one", "one"], "review_id": ["b", "a"], "review_score": [5, 1], "review_answer_timestamp": pd.to_datetime(["2018-05-03", "2018-05-01"])})
    result = first_reviews(reviews)
    assert result["review_score"].tolist() == [1]


def test_history_waits_for_delivery():
    frame = pd.DataFrame({
        "seller_id": ["a", "a", "a"], "customer_state": ["SP"] * 3, "category": ["test"] * 3,
        "order_purchase_timestamp": pd.to_datetime(["2018-01-01", "2018-01-05", "2018-01-11"]),
        "order_delivered_customer_date": pd.to_datetime(["2018-01-10", "2018-01-20", "2018-01-22"]),
        "late": [1, 0, 1],
    })
    result = add_history(frame)
    assert result["seller_past_count"].tolist() == [0, 0, 1]
    assert result["seller_past_late"].iloc[2] == pytest.approx(2 / 21)
    changed = frame.copy()
    changed.loc[1:, "late"] = 1 - changed.loc[1:, "late"]
    pd.testing.assert_series_equal(result["seller_past_late"], add_history(changed)["seller_past_late"])


def test_split_excludes_labels_unavailable_at_fit():
    frame = pd.DataFrame({
        "order_purchase_timestamp": pd.to_datetime(["2017-12-10", "2017-12-20", "2018-03-10", "2018-03-20", "2018-04-01"]),
        "order_delivered_customer_date": pd.to_datetime(["2017-12-15", "2018-01-05", "2018-03-15", "2018-04-05", "2018-04-10"]),
        "review_answer_timestamp": pd.to_datetime(["2017-12-15", "2018-01-05", "2018-03-15", "2018-04-05", "2018-09-02"]),
        "review_score": [5] * 5,
    })
    train, valid, test = time_split(frame)
    assert train.index.tolist() == [0]
    assert valid.index.tolist() == [2]
    assert test.index.tolist() == [4]
    assert np.isnan(test["review_score"].iloc[0])


def test_checkout_features_exclude_outcomes():
    forbidden = {"late", "delay_days", "review_score", "order_status", "order_approved_at", "shipping_limit_date", "order_delivered_carrier_date", "order_delivered_customer_date"}
    assert not set(FEATURES) & forbidden


def test_scenario_charges_all_affected_orders():
    result = financial_scenario(100, 1000, 80, 2000, success=0.5, fix_cost=3)
    assert result["fixed_late"] == 50
    assert result["implementation"] == 3000
    assert result["net"] == pytest.approx(50 * (0.5 * 8 + 0.2 * 20) - 3000)
    assert result["rating_uplift"] == pytest.approx(0.02)


def test_real_join_preserves_order_grain():
    frame, quality = load_orders()
    assert quality["raw_orders"] == 99441
    assert frame["order_id"].is_unique
    assert len(frame) == quality["eligible_delivered"]
    assert frame["review_score"].dropna().between(1, 5).all()
    assert frame["delay_days"].gt(0).eq(frame["late"].astype(bool)).all()
