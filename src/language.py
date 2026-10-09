import json
from pathlib import Path

ITALIAN = json.loads((Path(__file__).with_name('italian.json')).read_text(encoding='utf-8'))
CATEGORIES = json.loads((Path(__file__).with_name('categories.json')).read_text(encoding='utf-8'))


def translate(text, language='en', **values):
    return (ITALIAN[text] if language == 'it' else text).format(**values)


def number(value, digits=0, language='en'):
    result = f'{value:,.{digits}f}'
    if language == 'it':
        return result.replace(',', '|').replace('.', ',').replace('|', '.')
    return result


def category_name(code, language='en'):
    return CATEGORIES[code][language]
