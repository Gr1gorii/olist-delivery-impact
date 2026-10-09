import pandas as pd
import pytest
import statsmodels.formula.api as smf

from src.survey import survey_gap


def timing_sample():
    rows = []
    delivery = pd.Timestamp("2018-01-20 12:00")
    for seller in range(3):
        for delay in [1, 2, 6]:
            for before in [0, 1]:
                for repeat in range(3):
                    rows.append({
                        "seller_id": f"seller_{seller}", "seller_count": 1,
                        "late": 1, "delay_days": delay,
                        "order_delivered_customer_date": delivery,
                        "review_creation_date": delivery - pd.Timedelta(days=1) if before else delivery,
                        "review_answer_timestamp": delivery + pd.Timedelta(days=1),
                        "review_score": 4.5 + seller * 0.1 - delay * 0.1 - before * 0.7 + repeat * 0.01,
                    })
    return pd.DataFrame(rows)


def test_survey_gap_matches_seller_and_exact_delay_dummy_ols():
    sample = timing_sample()
    sample["before_delivery"] = sample["review_creation_date"].lt(sample["order_delivered_customer_date"]).astype(int)
    expected = smf.ols("review_score ~ before_delivery + C(seller_id) + C(delay_days)", sample).fit()
    result = survey_gap(sample)
    assert result["coefficient"] == pytest.approx(expected.params["before_delivery"], abs=1e-8)
    assert result["coefficient"] == pytest.approx(-0.7)
    assert result["orders"] == 54
    assert result["before_orders"] == result["after_orders"] == 27
    assert result["delay_days"] == [1, 2, 6]


def test_same_seller_day_check_excludes_cells_without_both_timings():
    sample = timing_sample()
    unshared_day = sample.iloc[[0]].copy()
    unshared_day["delay_days"] = 30
    unshared_seller = sample.iloc[[0]].copy()
    unshared_seller["seller_id"] = "different_seller"
    sample = pd.concat([sample, unshared_day, unshared_seller], ignore_index=True)
    result = survey_gap(sample, same_seller_day=True)
    assert result["orders"] == 54
    assert result["excluded_no_overlap"] == 2
    assert result["sellers"] == 3
    assert result["coefficient"] == pytest.approx(-0.7)


def test_creation_is_not_response_time_and_midnight_is_not_earlier_day():
    sample = timing_sample()
    before = sample["review_creation_date"].lt(sample["order_delivered_customer_date"])
    sample.loc[before, "review_creation_date"] = sample.loc[before, "order_delivered_customer_date"].dt.normalize()
    assert survey_gap(sample)["before_orders"] == 27
    with pytest.raises(ValueError, match="No comparable"):
        survey_gap(sample, calendar_day=True)
    with pytest.raises(ValueError, match="No comparable"):
        survey_gap(sample, time_column="review_answer_timestamp")


def test_timing_comparison_excludes_missing_and_multi_seller_rows():
    sample = timing_sample()
    missing_time = sample.iloc[[0]].copy()
    missing_time["review_creation_date"] = pd.NaT
    missing_delivery = sample.iloc[[0]].copy()
    missing_delivery["order_delivered_customer_date"] = pd.NaT
    multi_seller = sample.iloc[[0]].copy()
    multi_seller["seller_count"] = 2
    multi_seller["review_score"] = 999
    sample = pd.concat([sample, missing_time, missing_delivery, multi_seller], ignore_index=True)
    result = survey_gap(sample)
    assert result["input_orders"] == 54
    assert result["after_orders"] == 27
    assert result["coefficient"] == pytest.approx(-0.7)
