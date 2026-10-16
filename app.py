import json

import joblib
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from src.analysis import financial_scenario
from src.data import REPORTS, ROOT
from src.language import category_name, number, translate
from src.risk import FEATURES

DATA = ROOT / 'data' / 'processed' if (ROOT / 'data' / 'processed' / 'orders.parquet').exists() else ROOT / 'demo'
MODEL = ROOT / 'models' / 'late_risk.joblib' if (ROOT / 'models' / 'late_risk.joblib').exists() else ROOT / 'demo' / 'late_risk.joblib'

st.set_page_config(page_title='Olist', layout='wide')
language = st.selectbox('Language / Lingua', ['en', 'it'], format_func=lambda code: {'en': 'English', 'it': 'Italiano'}[code], key='language')


def t(text, **values):
    return translate(text, language, **values)


def n(value, digits=0):
    return number(value, digits, language)


@st.cache_data
def load_results(version):
    frame = pd.read_parquet(DATA / 'orders.parquet')
    summary = json.loads((REPORTS / 'summary.json').read_text())
    return frame, summary


@st.cache_resource
def load_model(version):
    return joblib.load(MODEL)


def chart(figure, height=360):
    figure.update_layout(template='plotly_white', font={'family': 'Arial', 'color': '#223c55'}, margin={'l': 10, 'r': 10, 't': 45, 'b': 10}, height=height, separators=',.' if language == 'it' else '.,')
    st.plotly_chart(figure, width='stretch', height=height, config={'displayModeBar': False})


def image(name):
    st.image(str(REPORTS / 'figures' / language / name), width='stretch')


if not (REPORTS / 'summary.json').exists():
    st.title(t('Olist | Delivery and reviews'))
    st.info(t('Prepare the results first: python scripts/download_data.py and python scripts/run_analysis.py --topics'))
    st.stop()

frame, summary = load_results((REPORTS / 'summary.json').stat().st_mtime_ns)
metric_source = pd.read_csv(REPORTS / 'model_metrics.csv')
selected_metric = metric_source.loc[metric_source['period'].eq('test') & metric_source['model'].str.startswith('Boosting')].iloc[0]
st.title(t('Olist | Delivery and reviews'))
st.caption(t('99,441 source orders | Brazil, 2016-2018 | Model test: April-July 2018'))
columns = st.columns(4)
columns[0].metric(t('Delivered orders'), n(len(frame)))
columns[1].metric(t('Average rating'), f"{n(summary['overall']['rating'], 2)} / 5")
columns[2].metric(t('Late deliveries'), f"{n(summary['overall']['late_rate'] * 100, 1)}%")
columns[3].metric(t('Lift over random selection'), f"{n(selected_metric['lift_at_10pct'], 2)}x", t('when reviewing 10% of orders'))
overview, complaints_tab, priorities_tab, risk_tab, money_tab = st.tabs([t('Overview'), t('Complaints'), t('Priorities'), t('Order risk'), t('Economics')])

with overview:
    st.subheader(t('Three findings'))
    comparisons = pd.read_csv(REPORTS / 'rating_comparison.csv')
    pooled = comparisons.iloc[0]
    timing = {row['review_time']: row['share'] for row in summary['reviews']['timing'] if row['population'] == 'all_late' and row['definition'] == 'timestamp'}
    st.info(t('**Delay penalty.** {threshold} stars at the late threshold and {slope}/day in days 1-7. This is observational, with seller fixed effects.\n\n**Survey timing.** {created}% of all late orders have a survey created before delivery; {answered}% have a response written before delivery.\n\n**Repeat purchases.** About {repeat}% repeat within 90 days. I find no demonstrated payback through repeat purchases. With zero repeat benefit, the base break-even budget is R$ {cost}/order.', threshold=n(pooled['threshold'], 2), slope=n(pooled['day_1_7'], 2), created=n(timing['creation'] * 100, 1), answered=n(timing['answer'] * 100, 1), repeat=n(summary['repeats']['repeat_rate'] * 100, 1), cost=n(summary['scenario']['break_even_cost'], 2)).replace('$', r'\$'))
    st.subheader(t('What I would test'))
    st.write(t('I would send the review survey after confirmed delivery, with a separate complaint channel available for orders still waiting to arrive. I would use the 2.59x-lift delay-risk ranking to send proactive delay notifications to the top-risk decile.'))
    with st.expander(t('A/B test design')):
        st.write(t('I would randomize by customer_unique_id at checkout, keep assignment stable across repeat orders, and use the first eligible order as the index order. A 2 × 2 test compares current vs confirmed-delivery survey timing and usual vs proactive notifications. I would stratify by pre-purchase risk decile and state.'))
        st.write(t('I would keep the complaint channel available in every arm. Only the top-risk decile receives the notification treatment, using a threshold fixed on an earlier cohort. The primary metric is mean first-review rating by 60 days after the original estimated delivery date; the notification effect is also reported in the preselected top decile.'))
        st.write(t('Secondary metrics are complaint contacts per 100 randomized index orders and the cancellation rate, including undelivered orders. I would also report review response and confirmed-delivery coverage, intervention costs and the interaction between treatments. A higher responder rating with lower review coverage would not establish better service. I would size the test before launch and analyze assigned groups with confidence intervals.'))
    st.subheader(t('Rating and delivery'))
    st.write(t('Late orders have an average rating of 2.27, compared with 4.29 for orders delivered on time. This is an observed association; an experiment is needed to measure the effect of improving delivery.'))
    c1, c2 = st.columns(2)
    state = c1.selectbox(t('Customer state'), [t('All')] + sorted(frame['customer_state'].unique()), key='state_filter')
    year = c2.selectbox(t('Purchase year'), [t('All'), '2017', '2018'], key='year_filter')
    view = frame.copy()
    if state != t('All'):
        view = view.loc[view['customer_state'].eq(state)]
    if year != t('All'):
        view = view.loc[view['order_purchase_timestamp'].dt.year.eq(int(year))]
    if view.empty:
        st.info(t('No delivered orders in this selection.'))
    else:
        st.caption(t('Selected: {orders} orders. The cards above show the full dataset.', orders=n(len(view))))
        c1, c2 = st.columns(2)
        with c1:
            ratings = view.groupby('late')['review_score'].mean().reset_index()
            ratings['delivery'] = ratings['late'].map({0: t('On time'), 1: t('Late')})
            ratings['rating_text'] = ratings['review_score'].map(lambda value: n(value, 2))
            figure = px.bar(ratings, x='delivery', y='review_score', color='delivery', text='rating_text', color_discrete_map={t('On time'): '#267b80', t('Late'): '#bf6b42'}, labels={'review_score': t('Average rating'), 'delivery': t('Delivery')})
            figure.update_traces(texttemplate='%{text}', textposition='outside')
            figure.update_layout(showlegend=False, yaxis_range=[0, 5])
            chart(figure, height=280)
        with c2:
            late = view.loc[view['late'].eq(1)].copy()
            late['days'] = late['delay_days'].clip(upper=31)
            chart(px.histogram(late, x='days', nbins=31, color_discrete_sequence=['#bf6b42'], labels={'days': t('Days late, 31 = 31 or more')}, title=t('Delay distribution')).update_yaxes(title=t('Number of orders')), height=280)
        monthly_view = view.loc[view['order_purchase_timestamp'].ge('2017-01-01') & view['order_purchase_timestamp'].lt('2018-08-01')]
        monthly = monthly_view.assign(month=monthly_view['order_purchase_timestamp'].dt.to_period('M').dt.to_timestamp()).groupby('month').agg(late=('late', 'mean'), orders=('order_id', 'size')).reset_index()
        chart(px.line(monthly, x='month', y='late', markers=True, hover_data=['orders'], color_discrete_sequence=['#223c55'], labels={'month': t('Purchase month'), 'late': t('Late delivery rate'), 'orders': t('Orders')}, title=t('Monthly cohorts: January 2017 - July 2018')).update_yaxes(tickformat='.0%').update_xaxes(tickformat='%m/%Y', hoverformat='%m/%Y'), height=260)
    comparisons = pd.read_csv(REPORTS / 'rating_comparison.csv')
    pooled = comparisons.iloc[0]
    st.write(t('Seller fixed effects separate the late threshold from the slope: {threshold} stars at the threshold and {slope} per day in days 1-7. The first late day combines both terms. These associations do not identify a causal effect.', threshold=n(pooled['threshold'], 2), slope=n(pooled['day_1_7'], 2)))
    st.caption(t('Survey creation precedes delivery for 5,334 of 6,534 late orders (81.6%). Creation dates are recorded at midnight; using strictly earlier calendar dates gives 72.7%. Creation is the survey invitation, not the written response.'))
    comparison_view = comparisons[['sample', 'reviews', 'raw_difference', 'threshold', 'first_day', 'day_1_7']].round(2).copy()
    comparison_view['sample'] = comparison_view['sample'].map({'all': t('All eligible reviews'), 'survey_before': t('Survey created before delivery'), 'survey_after': t('Survey created after delivery'), 'response_after': t('Response after delivery')})
    st.dataframe(comparison_view.rename(columns={'sample': t('Group'), 'reviews': t('Orders'), 'raw_difference': t('Raw difference'), 'threshold': t('Late threshold'), 'first_day': t('First late day'), 'day_1_7': t('Days 1-7 slope')}), hide_index=True, width='stretch')
    st.caption(t('Timing groups have different delay severity. Their coefficients are sensitivities, not causal comparisons. Multi-seller orders remain one review per order and are excluded from seller fixed effects.'))
    image('delay_effect.png')
    st.subheader(t('The "not yet received" gap'))
    survey = json.loads((REPORTS / 'survey_comparison.json').read_text())
    gap = survey['comparisons'][0]
    st.write(t('Among comparable late orders, survey creation before delivery is associated with {gap} stars (95% interval: {low} to {high}), holding seller and exact delay day fixed. The raw gap in the same sample is {raw} stars.', gap=n(gap['coefficient'], 2), low=n(gap['low'], 2), high=n(gap['high'], 2), raw=n(gap['raw_gap'], 2)))
    st.caption(t('I use {orders} pre-April 2018 single-seller late orders across {sellers} sellers, with both timing groups at delays of 1-6 or 8 days. Creation is the invitation date, not the written response. The comparison is observational and does not estimate the gain from postponing the survey.', orders=n(gap['orders']), sellers=n(gap['sellers'])))
    survey_view = pd.DataFrame(survey['comparisons'])
    survey_view['comparison'] = survey_view['comparison'].map({'creation': t('Creation timing'), 'creation_calendar': t('Creation, calendar-day sensitivity'), 'creation_same_seller_day': t('Creation, same seller and delay day'), 'response': t('Response timing')})
    survey_view['interval'] = survey_view.apply(lambda row: f"[{n(row['low'], 2)}, {n(row['high'], 2)}]", axis=1)
    st.dataframe(survey_view[['comparison', 'orders', 'sellers', 'coefficient', 'interval']].round(2).rename(columns={'comparison': t('Group'), 'orders': t('Orders'), 'sellers': t('Sellers'), 'coefficient': t('Before-delivery gap, stars'), 'interval': t('95% interval')}), hide_index=True, width='stretch')
    image('survey_gap.png')

with complaints_tab:
    st.subheader(t('What customers complain about'))
    st.caption(t('55,224 of 95,824 scored reviews have no nonblank title or message (57.6%). Topics describe only reviews with text; the clustering sample is narrower still: scores 1-2 and at least 15 characters.'))
    image('text_coverage.png')
    if (REPORTS / 'topics.csv').exists():
        topics = pd.read_csv(REPORTS / 'topics.csv')
        labels = json.loads((REPORTS / 'topic_labels.json').read_text())
        topics['label'] = topics['cluster'].map(lambda key: labels[str(key)]['label_it' if language == 'it' else 'label'])
        topics['family'] = topics['family'].map(t)
        st.caption(t('Reviews rated 1-2 with at least 15 characters. Topics use multilingual embeddings; names were checked on examples from before the test period. Each group describes a dominant theme and can contain other complaints.'))
        chart(px.bar(topics.sort_values('reviews'), x='reviews', y='label', orientation='h', color='family', color_discrete_map={t('Logistics'): '#267b80', t('Product'): '#223c55', t('Mixed'): '#82909c'}, labels={'reviews': t('Text reviews'), 'label': '', 'family': t('Group')}))
        choice = st.selectbox(t('Topic examples'), topics['cluster'].tolist(), format_func=lambda key: topics.set_index('cluster').loc[key, 'label'], key=f'topic_{language}')
        examples = pd.read_csv(REPORTS / 'review_translations.csv')
        examples = examples.loc[examples['cluster'].eq(choice)].merge(frame[['order_id', 'review_score', 'delay_days']], on='order_id', validate='one_to_one')
        st.caption(t('Translations of the five randomly sampled training reviews used in the manual audit. Original Portuguese text is available below each example. Translations are used only for display.'))
        for _, row in examples.iterrows():
            st.write(row[f'text_{language}'])
            st.caption(t('Rating: {score} | Difference from promised date: {days} days', score=int(row['review_score']), days=n(row['delay_days'])))
            with st.expander(t('Original review (Portuguese)')):
                st.write(row['text'])
        st.info(t('A review topic does not establish responsibility. Damage may occur during delivery, and a complaint about timing may be written before the order arrives.'))
    else:
        st.info(t('For topics, run python scripts/run_analysis.py --topics'))

with priorities_tab:
    st.subheader(t('Where I would start the audit'))
    st.write(t('Ten sellers and states SP, RJ, MG were selected by the number of late orders before 1 April 2018. Their union covers 565 of 1,006 test delays (56.2%) and includes 71.2% of test orders. This is a broad list for a process audit. Overlapping orders are counted once.'))
    image('priorities.png')
    sellers = pd.read_csv(REPORTS / 'sellers.csv')
    selected = sellers.loc[sellers['selected_before_test'], ['seller_id', 'orders', 'late_orders', 'late_rate', 'late_share', 'previous_late_orders']].sort_values('late_orders', ascending=False)
    seller_columns = {'seller_id': t('Seller ID'), 'orders': t('Orders'), 'late_orders': t('Late orders'), 'late_rate': t('Late delivery rate'), 'late_share': t('Share of all delays'), 'previous_late_orders': t('Delays before test')}
    st.caption(t('Sellers: single-seller orders only. A large contribution may reflect sales volume, so the delay rate is shown alongside it.'))
    st.dataframe(selected, hide_index=True, width='stretch', column_config={**seller_columns, 'late_rate': st.column_config.NumberColumn(t('Late delivery rate'), format='percent'), 'late_share': st.column_config.NumberColumn(t('Share of all delays'), format='percent')})
    st.download_button(t('Download selected sellers'), selected.rename(columns=seller_columns).to_csv(index=False), f'selected_sellers_{language}.csv', 'text/csv')
    regions = pd.read_csv(REPORTS / 'regions.csv')[['customer_state', 'orders', 'late_orders', 'late_rate', 'selected_before_test']]
    region_columns = {'customer_state': t('Customer state'), 'orders': t('Orders'), 'late_orders': t('Late orders'), 'late_rate': t('Late delivery rate'), 'selected_before_test': t('Selected before test')}
    st.dataframe(regions, hide_index=True, width='stretch', column_config={**region_columns, 'late_rate': st.column_config.NumberColumn(t('Late delivery rate'), format='percent')})
    st.download_button(t('Download states'), regions.rename(columns=region_columns).to_csv(index=False), f'states_{language}.csv', 'text/csv')

with risk_tab:
    st.subheader(t('Risk at checkout'))
    st.caption(t('Demo order dated 1 April 2018. History includes only deliveries before this date; the model was trained on outcomes available at that time.'))
    st.caption(t('The estimate applies to orders that will eventually be delivered. This model does not estimate cancellations or non-receipt.'))
    snapshot = frame.loc[frame['order_delivered_customer_date'].lt('2018-04-01')]
    seller_history = snapshot.groupby('seller_id')['late'].agg(['size', 'sum'])
    region_history = snapshot.groupby('customer_state')['late'].agg(['size', 'sum'])
    category_history = snapshot.groupby('category')['late'].agg(['size', 'sum'])
    seller_options = seller_history.sort_values('size', ascending=False).index.tolist()
    with st.form('checkout'):
        left, right = st.columns(2)
        seller = left.selectbox(t('Seller'), seller_options, key='seller')
        region = right.selectbox(t('Delivery state'), sorted(region_history.index), key='delivery_state')
        category = left.selectbox(t('Product category'), sorted(snapshot['category'].unique()), format_func=lambda code: category_name(code, language), key=f'category_{language}')
        price = right.number_input(t('Product value, R$'), min_value=1.0, value=140.0, step=10.0, key='price')
        freight = left.number_input(t('Freight, R$'), min_value=0.0, value=20.0, step=5.0, key='freight')
        promised = right.number_input(t('Promised time, calendar days'), min_value=1, max_value=90, value=20, key='promised')
        quantity = left.number_input(t('Number of items'), min_value=1, max_value=20, value=1, key='quantity')
        weight = right.number_input(t('Total weight, grams'), min_value=1.0, value=1000.0, step=100.0, key='weight')
        submitted = st.form_submit_button(t('Estimate risk'), key='score_order')
    if submitted:
        seller_state = snapshot.loc[snapshot['seller_id'].eq(seller), 'seller_state'].iloc[0]
        history = seller_history.loc[seller]
        area = region_history.loc[region]
        product_history = category_history.loc[category]
        row = {
            'log_price': np.log1p(price), 'freight_share': freight / price,
            'item_count': quantity, 'seller_count': 1, 'weight': weight,
            'promised_days': promised, 'purchase_month': 4, 'purchase_weekday': 6, 'purchase_hour': 12,
            'same_state': int(seller_state == region), 'seller_past_count': history['size'],
            'seller_past_late': (history['sum'] + 1) / (history['size'] + 20),
            'region_past_count': area['size'], 'region_past_late': (area['sum'] + 1) / (area['size'] + 20),
            'category_past_count': product_history['size'], 'category_past_late': (product_history['sum'] + 1) / (product_history['size'] + 20),
            'customer_state': region, 'seller_state': seller_state, 'category': category,
        }
        probability = load_model(MODEL.stat().st_mtime_ns).predict_proba(pd.DataFrame([row])[FEATURES])[0, 1]
        st.metric(t('Estimated probability of delay'), f'{n(probability * 100, 1)}%')
        st.caption(t('The estimate helps prioritize reviews. This 2018 model needs retraining and calibration checks before use on new orders.'))
    image('risk_validation.png')
    st.write(t('Reviewing 10% of orders finds {recall}% of delays. The remaining {missed}% fall outside this queue.', recall=n(selected_metric['recall_at_10pct'] * 100, 1), missed=n((1 - selected_metric['recall_at_10pct']) * 100, 1)))
    metrics = pd.read_csv(REPORTS / 'model_metrics.csv')
    metrics['model'] = metrics['model'].map(t)
    metrics['period'] = metrics['period'].map(t)
    metric_columns = {'model': t('Model'), 'period': t('Period'), 'orders': t('Orders'), 'late_rate': t('Late delivery rate'), 'average_precision': 'Average Precision', 'roc_auc': 'ROC AUC', 'brier': 'Brier', 'precision_at_10pct': t('Precision at 10%'), 'recall_at_10pct': t('Recall at 10%'), 'lift_at_10pct': t('Lift at 10%')}
    for column in ['late_rate', 'precision_at_10pct', 'recall_at_10pct']:
        metrics[column] = metrics[column].map(lambda value: f'{n(value * 100, 1)}%')
    for column, digits in [('average_precision', 3), ('roc_auc', 3), ('brier', 4), ('lift_at_10pct', 2)]:
        metrics[column] = metrics[column].map(lambda value: n(value, digits))
    metrics = metrics.rename(columns=metric_columns)
    st.dataframe(metrics, hide_index=True, width='stretch')

with money_tab:
    st.subheader(t('How much I could spend on improvement'))
    st.caption(t('Scenario for 18,359 orders from the selected sellers and states, April-July 2018. The rates below are assumptions; Olist has no support or compensation costs.'))
    left, right = st.columns(2)
    success = left.slider(t('Delays resolved, %'), 0, 100, 50, 5, key='success') / 100
    cost = right.number_input(t('Improvement cost per order in the group, R$'), min_value=0.0, value=3.0, step=0.1, key='fix_cost')
    contact_cost = left.number_input(t('Cost per support contact, R$'), min_value=0.0, value=8.0, key='contact_cost')
    compensation = right.number_input(t('Average compensation, R$'), min_value=0.0, value=20.0, key='compensation')
    repeat = left.slider(t('Additional repeat purchases, %'), 0, 10, 0, key='repeat') / 100
    margin = right.slider(t('Repeat purchase margin, %'), 0, 50, 15, key='margin') / 100
    source = summary['scenario']
    result = financial_scenario(source['target_late'], source['affected_orders'], source['gain_sum'], source['all_reviews'], success=success, contact_cost=contact_cost, compensation=compensation, repeat_uplift=repeat, margin=margin, fix_cost=cost, late_customer_counts=source['late_customer_counts'])
    a, b, c = st.columns(3)
    a.metric(t('Scenario net result'), f"R$ {n(result['net'])}")
    b.metric(t('Break-even cost per order'), f"R$ {n(result['break_even_cost'], 2)}")
    alternative = source['gain_sum_after_delivery'] * success / source['all_reviews']
    c.metric(t('Scenario rating increase'), f"+{n(alternative, 3)} ... +{n(result['rating_uplift'], 3)}")
    parts = pd.DataFrame({'item': [t('Support'), t('Compensation'), t('Repeat purchase margin'), t('Improvement cost')], 'R$': [result['support'], result['compensation'], result['repeat_margin'], -result['implementation']]})
    chart(px.bar(parts, x='item', y='R$', text_auto='.0f', color_discrete_sequence=['#223c55'], labels={'item': t('Item')}))
    st.write(t('Formula: resolved late orders × (50% × contact cost + 20% × compensation) + expected unique buyers helped × assumed repeat uplift × R$ 140 × margin - all selected orders × improvement cost.'))
    st.caption(t('I count each customer_unique_id once for repeat benefits, even with several delayed orders. The rating figures compare pooled and post-survey fits; they are not confidence bounds or promised gains. Unsupported orders receive zero rating gain.'))
    st.caption(t('Base repeat benefit is zero. The observed 90-day repeat rate is about 1.0% among 72,373 unique buyers with complete follow-up. The 0.3 percentage-point difference between on-time and late buyers is descriptive, not an intervention effect.'))
    st.caption(t('The chart below uses the base rates and assumes that 50% of delays are resolved.'))
    image('financial_sensitivity.png')
