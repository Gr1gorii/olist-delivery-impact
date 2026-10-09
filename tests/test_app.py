import ast
import json
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from src.language import translate

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('language', ['en', 'it'])
def test_demo_scores_checkout_and_updates_scenario(language):
    app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=30).run()
    app.selectbox(key='language').set_value(language).run()
    assert not app.exception
    assert len(app.tabs) == 5
    assert app.tabs[0].label == translate('Overview', language)
    assert app.selectbox(key='state_filter').value == translate('All', language)
    assert app.selectbox(key='year_filter').value == translate('All', language)
    app.button(key='score_order').click().run()
    label = translate('Estimated probability of delay', language)
    probabilities = [metric.value for metric in app.metric if metric.label == label]
    assert len(probabilities) == 1
    probability = float(probabilities[0].rstrip('%').replace(',', '.'))
    assert 0 < probability < 100
    assert app.slider(key='repeat').value == 0
    findings = next(item.value for item in app.info if ('Delay penalty' if language == 'en' else 'Penalità del ritardo') in item.value)
    assert ('-0.50' if language == 'en' else '-0,50') in findings
    assert ('-0.30' if language == 'en' else '-0,30') in findings
    assert ('81.6' if language == 'en' else '81,6') in findings
    assert ('68.5' if language == 'en' else '68,5') in findings
    assert ('0.12' if language == 'en' else '0,12') in findings
    assert translate('A/B test design', language) in [item.label for item in app.expander]
    gap = next(item.value for item in app.markdown if ('Among comparable late orders' if language == 'en' else 'Tra ordini in ritardo confrontabili') in item.value)
    assert ('-1.06' if language == 'en' else '-1,06') in gap
    app.slider(key='success').set_value(0).run()
    label = translate('Scenario rating increase', language)
    gains = [metric.value for metric in app.metric if metric.label == label]
    expected = '+0,000 ... +0,000' if language == 'it' else '+0.000 ... +0.000'
    assert gains == [expected]
    assert not app.exception


def test_language_catalog_covers_display_content():
    italian = json.loads((ROOT / 'src/italian.json').read_text())
    for filename in ['app.py', 'scripts/make_figures.py']:
        tree = ast.parse((ROOT / filename).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 't':
                if node.args and isinstance(node.args[0], ast.Constant):
                    assert node.args[0].value in italian
    categories = json.loads((ROOT / 'src/categories.json').read_text())
    orders = pd.read_parquet(ROOT / 'data/processed/orders.parquet', columns=['category'])
    assert set(orders.category.unique()) <= set(categories)
    assert all(labels['en'] and labels['it'] for labels in categories.values())
    examples = pd.read_csv(ROOT / 'reports/review_translations.csv')
    audit = pd.read_csv(ROOT / 'reports/topic_audit.csv')
    assert examples.order_id.tolist() == audit.order_id.tolist()
    assert examples.text.tolist() == audit.text.tolist()
    assert examples[['text_en', 'text_it']].notna().all().all()
    topics = pd.read_csv(ROOT / 'reports/topics.csv')
    assert set(topics.family) <= set(italian)
