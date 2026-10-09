import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.analysis import financial_scenario, priorities, rating_model, rating_comparison, scenario_inputs
from src.data import REPORTS, ROOT, add_history, load_orders
from src.language import translate
from src.diagnostics import review_diagnostics, repeat_purchases
from src.risk import train_risk


def main():
    parser = argparse.ArgumentParser(description="Recalculate the analysis / Ricalcola l’analisi")
    parser.add_argument("--language", choices=["en", "it"], default="en", help="Message language / Lingua dei messaggi")
    parser.add_argument("--topics", action="store_true", help="Include complaint topics / Include i temi dei reclami")
    args = parser.parse_args()
    t = lambda text: translate(text, args.language)
    REPORTS.mkdir(exist_ok=True)
    (ROOT / "data" / "processed").mkdir(exist_ok=True)
    (ROOT / "models").mkdir(exist_ok=True)
    print(t('1/4: preparing orders'), flush=True)
    frame, quality = load_orders()
    frame = add_history(frame)
    reviews = review_diagnostics(frame)
    repeats = repeat_purchases(frame)
    frame.to_parquet(ROOT / "data" / "processed" / "orders.parquet", index=False)
    print(t('2/4: temporal risk validation'), flush=True)
    scores, test, refit, splits = train_risk(frame)
    scores.to_csv(REPORTS / "model_metrics.csv", index=False)
    print(t('3/4: ratings and priorities'), flush=True)
    rating_train = refit.loc[refit["review_answer_timestamp"].lt("2018-04-01")]
    model, coefficients = rating_model(rating_train)
    coefficients.to_csv(REPORTS / "rating_coefficients.csv", index=False)
    before_sample = rating_train.loc[rating_train["review_creation_date"].lt(rating_train["order_delivered_customer_date"])]
    after_sample = rating_train.loc[rating_train["review_creation_date"].ge(rating_train["order_delivered_customer_date"])]
    response_sample = rating_train.loc[rating_train["review_answer_timestamp"].ge(rating_train["order_delivered_customer_date"])]
    before_model, before_coefficients = rating_model(before_sample)
    post_model, post_coefficients = rating_model(after_sample)
    response_model, response_coefficients = rating_model(response_sample)
    before_coefficients.to_csv(REPORTS / "rating_before_delivery.csv", index=False)
    post_coefficients.to_csv(REPORTS / "rating_after_delivery.csv", index=False)
    response_coefficients.to_csv(REPORTS / "rating_after_response.csv", index=False)
    comparisons = pd.DataFrame([
        rating_comparison(model, "all"), rating_comparison(before_model, "survey_before"),
        rating_comparison(post_model, "survey_after"), rating_comparison(response_model, "response_after"),
    ])
    comparisons.to_csv(REPORTS / "rating_comparison.csv", index=False)
    single_old = refit.loc[refit["seller_count"].eq(1)]
    single_test = test.loc[test["seller_count"].eq(1)]
    seller_table, sellers = priorities(single_old, single_test, "seller_id", 10, 100)
    region_table, regions = priorities(refit, test, "customer_state", 3, 200)
    seller_table.to_csv(REPORTS / "sellers.csv", index=False)
    region_table.to_csv(REPORTS / "regions.csv", index=False)
    test, unsupported = scenario_inputs(test, model, sellers, regions)
    alternative, post_unsupported = scenario_inputs(test, post_model, sellers, regions)
    test["rating_gain_after_delivery"] = alternative["rating_gain"]
    test.loc[test["seller_count"].gt(1) & ~test["customer_state"].isin(regions), "targeted"] = False
    target = test["targeted"]
    gain_sum = test.loc[target & test["review_score"].notna(), "rating_gain"].sum()
    late_customers = test.loc[target & test["late"].eq(1)].groupby("customer_unique_id").size().tolist()
    finance = financial_scenario(test.loc[target, "late"].sum(), target.sum(), gain_sum, test["review_score"].notna().sum(), late_customer_counts=late_customers)
    finance["late_customer_counts"] = late_customers
    finance["target_late_customers"] = len(late_customers)
    finance["gain_sum"] = float(gain_sum)
    finance["gain_sum_after_delivery"] = float(test.loc[target & test["review_score"].notna(), "rating_gain_after_delivery"].sum())
    finance["all_reviews"] = int(test["review_score"].notna().sum())
    finance["rating_uplift_after_delivery"] = finance["gain_sum_after_delivery"] * finance["success"] / finance["all_reviews"]
    finance["target_late_share"] = float(test.loc[target, "late"].sum() / test["late"].sum())
    finance["average_basket_observed"] = float(test["price"].mean())
    finance["unsupported_rating_orders"] = unsupported
    finance["unsupported_after_delivery_orders"] = post_unsupported
    test.to_parquet(ROOT / "data" / "processed" / "test_orders.parquet", index=False)
    late_summary = frame.dropna(subset=["review_score"]).groupby("late").agg(orders=("order_id", "size"), rating=("review_score", "mean"), low_score=("review_score", lambda s: s.le(2).mean())).reset_index()
    late_summary.to_csv(REPORTS / "rating_by_delivery.csv", index=False)
    summary = {
        "quality": quality, "splits": splits, "reviews": reviews, "repeats": repeats,
        "overall": {"rating": float(frame["review_score"].mean()), "late_rate": float(frame["late"].mean()), "late_orders": int(frame["late"].sum())},
        "rating_model": {"orders": len(model["sample"]), "r_squared": model["result"].rsquared, "post_delivery_orders": len(post_model["sample"]), "comparisons": comparisons.to_dict("records"), "seller_fixed_effects": True},
        "priorities": {"sellers": sellers, "regions": regions}, "scenario": finance,
    }
    (REPORTS / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.topics:
        print(t('4/4: multilingual complaint embeddings'), flush=True)
        from src.topics import cluster_complaints
        cluster_complaints(frame)
    print(scores.to_string(index=False), flush=True)
    print(json.dumps({key: value for key, value in finance.items() if key != "late_customer_counts"}, indent=2), flush=True)


if __name__ == "__main__":
    main()
