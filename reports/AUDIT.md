# Audit handoff

This record describes the preceding audit pass. The latest presentation polish, same-delay timing comparison and A/B test plan are in the [current README](../README.md). Existing models are unchanged; the final project has 24 passing tests.

**Share with caveats.** All seven requested questions are addressed and repairs were made. The review is partial only for exhaustive browser interaction coverage. Scoped totals below are inventory counts, not a certification that every possible state was tested.

## Findings and verified fixes

1. Checkout history lacked category rates; snapshot availability was not proven. **Fixed:** category history, strict earlier purchase/delivery tests and all 19 features documented. Temporal lift changes from 2.87x to 2.59x.

2. Repeat benefit was an assumption without a measured buyer cohort. **Fixed:** customer_unique_id, mature 90-day cohort 754/72,373 repeats, default uplift zero and each buyer counted once.

3. Response timing had been used instead of survey creation; clustered errors were not seller fixed effects. **Fixed:**81.63% creation-before-delivery among all late orders, calendar-day sensitivity 72.74%, before/after fits and seller fixed effects. Raw gap -2.031 versus adjusted first day -0.800; associations remain noncausal.

4. Text selection and shared-review attribution were incomplete. **Fixed:**57.63% without text, score distributions, text-only topic scope, one review per order and single-seller-only fixed effects/rankings.

5. The revised zero-delay scenario rebuilt day terms from the original delay. **Fixed:** full delay reset and regression test. Final gain +0.0066 to +0.0165 stars; base net -R$52,817, break-even R$0.1231/order.

6. Binary ignore rules were missing. **Fixed:** raw data, models, prepared Parquet and embeddings ignored; checked with git check-ignore in an isolated temporary repository. Kaggle script/checksums and bilingual CC BY-NC-SA 4.0 attribution verified. This project itself has no Git metadata.

## Dashboard quality

| Category | Observed defects | Assessment |
| --- | --- | --- |
| Dashboard usefulness and completeness | 0 / 7 | All seven audit questions addressed. Live operational calibration and causal responsibility require further data. |
| Analytical clarity | 0 / 7 | All requested comparisons present in both READMEs; threshold and slope separated. |
| Visual and interaction consistency | 0 / 9 | Static figures inspected in both languages and overview captured. Automated bilingual form/scenario checks pass; all browser filter combinations not exhaustively inspected. |

## Analytical correctness

| Category | Observed defects | Assessment |
| --- | --- | --- |
| Source authority and confidence | 0 / 7 | Official Olist source and license checked. Catalog/promise snapshot versions unavailable; checkout availability remains assumed. |
| SQL/value accuracy | 0 / 6 | Raw counts, FE regression equivalence, repeat identities, scenario algebra and temporal test reconciled. |
| Within-chart agreement | 0 / 8 | Both language figure sets inspected; headlines, legends and intervals agree with regenerated tables. |
| Complete source details | 0 / 8 | Figure notes provide population, period and method; missing-text notes are completed by linked README source and denominators. |
| Cross-artifact consistency | 0 / 9 | READMEs, summary, app and figures use rerun results. Screenshots and executed notebooks refreshed. |
| Data-quality controls | 0 / 7 | Strict historical cutoffs, midnight timing sensitivity, missing text, multi-seller ambiguity and mature follow-up tested. |
| Conclusion support | 0 / 6 | Causal and financial claims narrowed to observed associations and assumption-based scenarios. No realized saving claim. |

[Full report](../README.md). 20 tests passed; both notebooks executed without errors.
