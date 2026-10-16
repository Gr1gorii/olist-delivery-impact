# Dataset attribution and license

[English](DATA_LICENSE.md) | [Italiano](DATA_LICENSE.it.md)

I use the [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), published by Olist on Kaggle. The source contains anonymized Brazilian marketplace orders from 2016 to 2018.

The dataset is licensed under [Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International, CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/). I retain this attribution, use the dataset for a noncommercial educational analysis, and apply the same license to adaptations of the dataset, including the prepared data, translated review examples and data-based figures. This notice concerns the data and its adaptations; it does not grant additional rights to the source data.

I aggregate items into orders, retain the first answered review for each order, derive delivery and historical features, and translate selected review examples for display. The original review texts remain in Portuguese. The reports document the filters and calculations used to produce the results.

I download the source tables with:

```bash
python scripts/download_data.py
```

The download script records SHA-256 checksums in `data/manifest.json`. I exclude raw tables, prepared Parquet datasets, embedding arrays and model binaries from Git through `.gitignore`. The current delivery is a project folder without Git metadata; the exclusions describe what a future repository should contain, rather than a claim that tracked files have been removed.

Before redistributing adapted data, I preserve the source attribution and license notice, identify my changes, and follow the noncommercial and share-alike terms. I do not imply endorsement by Olist.

The public app includes a reduced snapshot in `demo/orders.parquet`: ten fields used for the charts and historical seller, category and state summaries. It excludes customer identifiers, locations below state level, review text and embedding arrays. This adapted snapshot uses the same CC BY-NC-SA 4.0 license and Olist attribution above. The fitted delay model is included in `demo/late_risk.joblib` for the checkout example.
