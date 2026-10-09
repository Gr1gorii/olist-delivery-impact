import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.data import REPORTS, ROOT
from src.survey import survey_gap


def main():
    frame = pd.read_parquet(ROOT / "data/processed/orders.parquet")
    sample = frame.loc[
        frame["order_purchase_timestamp"].lt("2018-04-01")
        & frame["order_delivered_customer_date"].lt("2018-04-01")
        & frame["review_answer_timestamp"].lt("2018-04-01")
    ]
    rows = []
    for name, column, calendar, matched in [
        ("creation", "review_creation_date", False, False),
        ("creation_calendar", "review_creation_date", True, False),
        ("creation_same_seller_day", "review_creation_date", False, True),
        ("response", "review_answer_timestamp", False, False),
    ]:
        rows.append({"comparison": name, **survey_gap(sample, column, calendar, matched)})
    pd.DataFrame([{key: value for key, value in row.items() if key != "delay_days"} for row in rows]).to_csv(REPORTS / "not_received_penalty.csv", index=False)
    (REPORTS / "survey_comparison.json").write_text(json.dumps({
        "purchase_delivery_response_before": "2018-04-01",
        "population": "Late delivered orders with a first scored review and one seller",
        "comparisons": rows,
    }, indent=2) + "\n")
    print(pd.DataFrame(rows)[["comparison", "orders", "sellers", "coefficient", "low", "high"]].to_string(index=False))


if __name__ == "__main__":
    main()
