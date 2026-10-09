import json
import textwrap
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, ScalarFormatter
import numpy as np
import pandas as pd
from sklearn.metrics import precision_recall_curve

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.data import REPORTS, ROOT
from src.language import translate, number

LANGUAGE = "en"


def t(text, **values):
    return translate(text, LANGUAGE, **values)

BLUE = "#223c55"
TEAL = "#267b80"
ORANGE = "#bf6b42"
GREY = "#82909c"
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 11, "axes.unicode_minus": False,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.labelcolor": BLUE, "text.color": BLUE, "axes.titleweight": "bold",
    "axes.edgecolor": "#ccd3d8", "grid.color": "#e8ecef",
    "figure.facecolor": "white", "axes.facecolor": "white", "savefig.dpi": 180,
})


def save(fig, name, note):
    if LANGUAGE == "it":
        for ax in fig.axes:
            for axis in [ax.xaxis, ax.yaxis]:
                if isinstance(axis.get_major_formatter(), ScalarFormatter):
                    axis.set_major_formatter(FuncFormatter(lambda value, pos: f"{value:g}".replace(".", ",")))
    fig.text(0.02, 0.015, textwrap.fill(note, width=int(fig.get_figwidth() * 11)), fontsize=8.5, color=GREY)
    fig.tight_layout(rect=(0.01, 0.09, 0.99, 0.96))
    folder = REPORTS / "figures" / LANGUAGE
    folder.mkdir(parents=True, exist_ok=True)
    fig.savefig(folder / name, facecolor="white")
    plt.close(fig)


def main(language="en"):
    global LANGUAGE
    LANGUAGE = language
    frame = pd.read_parquet(ROOT / "data" / "processed" / "orders.parquet")
    test = pd.read_parquet(ROOT / "data" / "processed" / "test_orders.parquet")
    summary = json.loads((REPORTS / "summary.json").read_text())
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.7), gridspec_kw={"width_ratios": [1, 1.6]})
    means = frame.groupby("late")["review_score"].mean()
    bars = axes[0].bar([t('On time'), t('Late')], means.values, color=[TEAL, ORANGE], width=0.55)
    axes[0].bar_label(bars, labels=[number(v, 2, LANGUAGE) for v in means], padding=6, fontsize=16, fontweight="bold")
    axes[0].set(ylim=(0, 5), ylabel=t('Average rating, stars'), title=t('Rating and delivery time'))
    distribution = pd.crosstab(frame["review_score"], frame["late"], normalize="columns") * 100
    positions = np.arange(5)
    axes[1].bar(positions - 0.18, distribution[0], width=0.36, color=TEAL, label=t('On time'))
    axes[1].bar(positions + 0.18, distribution[1], width=0.36, color=ORANGE, label=t('Late'))
    axes[1].set(xticks=positions, xticklabels=[1, 2, 3, 4, 5], xlabel=t('Rating, stars'), ylabel=t('Share of reviews within group, %'), title=t('Rating distribution'))
    axes[1].legend(frameon=False)
    save(fig, "rating_overview.png", t('Olist, 2016-2018. Delivered orders with a first review: 95,824. Association does not establish causality.'))

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    sample = frame.loc[frame["order_purchase_timestamp"].lt("2018-04-01") & frame["order_delivered_customer_date"].lt("2018-04-01") & frame["review_answer_timestamp"].lt("2018-04-01")]
    daily = sample.groupby("delay_days")["review_score"].agg(["mean", "count", "std"])
    daily = daily.loc[0:21]
    error = 1.96 * daily["std"] / np.sqrt(daily["count"])
    axes[0].errorbar(daily.index, daily["mean"], yerr=error, color=BLUE, marker="o", markersize=4, capsize=2)
    axes[0].set(xlabel=t('Days after promised date'), ylabel=t('Average rating, stars'), ylim=(1, 5), title=t('Ratings fall in the first week'))
    for file, label, color, offset in [("rating_coefficients.csv", t('All eligible reviews'), BLUE, -0.16), ("rating_before_delivery.csv", t('Survey before delivery'), TEAL, 0), ("rating_after_delivery.csv", t('Survey after delivery'), ORANGE, 0.16)]:
        coefficients = pd.read_csv(REPORTS / file)
        axes[1].errorbar(coefficients["coefficient"], np.arange(4) + offset, xerr=[coefficients["coefficient"] - coefficients["low"], coefficients["high"] - coefficients["coefficient"]], fmt="o", color=color, capsize=4, label=label)
    axes[1].axvline(0, color=GREY, lw=1)
    axes[1].set(yticks=np.arange(4), yticklabels=[t('Late threshold'), t('Days 1-7'), t('Days 8-14'), t('Days 15-30')], xlabel=t('Threshold in stars; slopes in stars/day'), title=t('The estimate depends on the sample'))
    axes[1].invert_yaxis()
    axes[1].legend(frameon=False, loc="upper left", bbox_to_anchor=(0.01, 0.70), fontsize=9)
    save(fig, "delay_effect.png", t('Before 1 April 2018. Left: raw means, 95% intervals. Right: single-seller fixed-effect OLS, seller-clustered 95% intervals. Missing points are unestimable; timing groups differ in severity.'))

    survey_file = REPORTS / "survey_comparison.json"
    if survey_file.exists():
        survey = pd.DataFrame(json.loads(survey_file.read_text())["comparisons"])
        labels = [t('Creation: same delay and seller'), t('Creation: calendar-day sensitivity'), t('Creation: same seller and delay cell'), t('Written response: same delay and seller')]
        fig, ax = plt.subplots(figsize=(12, 5.1))
        positions = np.arange(len(survey))
        ax.errorbar(survey['coefficient'], positions, xerr=[survey['coefficient'] - survey['low'], survey['high'] - survey['coefficient']], fmt='o', color=BLUE, capsize=4)
        for position, row in survey.iterrows():
            ax.text(0.02, position, number(row['coefficient'], 2, LANGUAGE), va='center', fontsize=11)
        ax.axvline(0, color=GREY, linewidth=1)
        ax.set(yticks=positions, yticklabels=labels, xlim=(-2.5, 0.4), xlabel=t('Before-delivery minus after-delivery score, stars'), title=t('The "not yet received" gap is observational'))
        ax.invert_yaxis()
        save(fig, 'survey_gap.png', t('Olist, before 1 April 2018, late single-seller orders. Seller-clustered 95% intervals; shared delay days only. Creation is the invitation, not the written response.'))

    fig, ax = plt.subplots(figsize=(10, 4.7))
    scored = frame.dropna(subset=['review_score'])
    distribution = pd.crosstab(scored['review_score'], scored['has_text'], normalize='columns') * 100
    positions = np.arange(5)
    ax.bar(positions - 0.18, distribution[False], width=0.36, color=GREY, label=t('Without text'))
    ax.bar(positions + 0.18, distribution[True], width=0.36, color=BLUE, label=t('With text'))
    ax.set(xticks=positions, xticklabels=[1, 2, 3, 4, 5], xlabel=t('Rating, stars'), ylabel=t('Share of reviews within group, %'), title=t('57.6% of scored reviews have no text'))
    ax.legend(frameon=False)
    save(fig, 'text_coverage.png', t('Nonblank title or message counts as text. Topics cover only text reviews; scores differ across these groups.'))

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    late = frame.loc[frame["late"].eq(1), "delay_days"]
    axes[0].hist(late.clip(upper=31), bins=np.arange(0.5, 32.5, 1), color=ORANGE, edgecolor="white")
    axes[0].set(xlabel=t('Days late, 31 = 31 days or more'), ylabel=t('Number of orders'), title=t('Length of delays'))
    monthly = frame.assign(month=frame["order_purchase_timestamp"].dt.to_period("M").astype(str)).groupby("month")["late"].agg(["mean", "size"])
    monthly = monthly.loc["2017-01":"2018-07"]
    axes[1].plot(np.arange(len(monthly)), monthly["mean"] * 100, marker="o", color=BLUE)
    ticks = [0, 3, 6, 9, 12, 15, 18]
    axes[1].set(xticks=ticks, xticklabels=monthly.index[ticks], ylabel=t('Late delivery rate, %'), ylim=(0, max(monthly["mean"]) * 115), title=t('Risk changes across months'))
    axes[1].tick_params(axis="x", labelrotation=30)
    save(fig, "delay_distribution.png", t('Olist, delivered orders. Cohorts by purchase month; cancellations and undelivered orders excluded.'))

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    regions = pd.read_csv(REPORTS / "regions.csv").head(8).iloc[::-1]
    bars = axes[0].barh(regions["customer_state"], regions["late_orders"], color=[BLUE if x else GREY for x in regions["selected_before_test"]])
    axes[0].bar_label(bars, padding=4)
    axes[0].set(xlabel=t('Late orders'), title=t('Customer states'))
    axes[0].set_xlim(0, regions["late_orders"].max() * 1.18)
    sellers = pd.read_csv(REPORTS / "sellers.csv")
    sellers = sellers.loc[sellers["selected_before_test"]].sort_values("late_orders").tail(10)
    bars = axes[1].barh(sellers["seller_id"].str[:8], sellers["late_orders"], color=BLUE)
    axes[1].bar_label(bars, padding=4)
    axes[1].set(xlabel=t('Late orders'), title=t('10 sellers selected before the test'))
    axes[1].set_xlim(0, sellers["late_orders"].max() * 1.25)
    save(fig, "priorities.png", t('Test: April-July 2018. Blue indicates priorities selected before 1 April. Sellers: single-seller orders only.'))

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    precision, recall, _ = precision_recall_curve(test["late"], test["risk"])
    axes[0].plot(recall, precision, color=BLUE, label="Boosting 15")
    axes[0].axhline(test["late"].mean(), color=GREY, ls="--", label=t('Random selection'))
    axes[0].set(xlim=(0, 1), ylim=(0, 0.5), xlabel=t('Share of delays found, recall'), ylabel=t('Delays among selected orders, precision'), title=t('Risk ranking performance'))
    axes[0].legend(frameon=False)
    scores = pd.read_csv(REPORTS / "model_metrics.csv")
    scores = scores.loc[scores["period"].eq("test")]
    bars = axes[1].bar([t('Random'), t('Logistic\nregression'), t('Boosting')], scores["precision_at_10pct"] * 100, color=[GREY, TEAL, BLUE], width=0.6)
    axes[1].bar_label(bars, labels=[number(v * 100, 1, LANGUAGE) + "%" for v in scores["precision_at_10pct"]], padding=5, fontsize=13)
    axes[1].set(ylim=(0, 14), ylabel=t('Delays among the selected 10% of orders, %'), title=t('{lift} times the random precision', lift=number(scores.iloc[-1]['lift_at_10pct'], 2, LANGUAGE)))
    save(fig, "risk_validation.png", t('Test: 25,777 orders, April-July 2018. Ranking uses checkout features. Left precision axis: 0-50%.'))

    fig, ax = plt.subplots(figsize=(10, 4.6))
    scenario = summary["scenario"]
    costs = np.linspace(0, 0.5, 100)
    benefit = scenario["support"] + scenario["compensation"] + scenario["repeat_margin"]
    net = benefit - scenario["affected_orders"] * costs
    ax.plot(costs, net, color=BLUE, lw=2)
    ax.axhline(0, color=GREY, lw=1)
    ax.axvline(scenario["break_even_cost"], color=ORANGE, ls="--")
    ax.annotate(t("Break-even: R$ {cost} / order", cost=number(scenario["break_even_cost"], 2, LANGUAGE)), (scenario["break_even_cost"], 0), xytext=(0.19, benefit * 0.62), arrowprops={"arrowstyle": "->", "color": ORANGE}, fontsize=11)
    ax.set(xlabel=t('Improvement cost per order in the selected group, R$'), ylabel=t('Scenario net result over 4 months, R$'), title=t('A broad intervention needs a low cost to break even'))
    save(fig, "financial_sensitivity.png", t('April-July 2018, 18,359 selected orders. Resolving 50% of delays; financial rates are assumptions.'))

    topics_file = REPORTS / "topics.csv"
    if topics_file.exists():
        topics = pd.read_csv(topics_file).sort_values("reviews")
        if LANGUAGE == "it":
            topics["label"] = topics["label_it"]
        fig, ax = plt.subplots(figsize=(11, max(4.5, len(topics) * 0.42)))
        bars = ax.barh(topics["label"], topics["reviews"], color=[TEAL if value == 'Logistics' else BLUE if value == 'Product' else GREY for value in topics["family"]])
        ax.bar_label(bars, labels=[number(v, 0, LANGUAGE) for v in topics["reviews"]], padding=5)
        ax.set_xlim(0, topics["reviews"].max() * 1.2)
        ax.set(xlabel=t('Number of text reviews rated 1-2'), title=t('What customers complain about'))
        save(fig, "complaints.png", t('Olist, 2016-2018. Names describe dominant themes. Blue: product. Teal: delivery. Grey: mixed.'))


if __name__ == "__main__":
    for language in ["en", "it"]:
        main(language)
