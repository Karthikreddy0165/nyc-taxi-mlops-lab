# 009: Training window and holdout month

Stage: S2 · Date: 2026-11-21 · Author: karthik · Drafted by agent: yes

## Choice

Train on a 3-month window from January 2024 through March 2024 (`2024-01..2024-03`) and evaluate exclusively on the subsequent unseen month, April 2024 (`2024-04`), as the holdout dataset. The historical zone-pair median distance lookup (`est_distance_miles`) must be computed strictly from the training window (`2024-01..2024-03`) and never incorporate trips from the holdout month.

## Rejected alternative

Random k-fold train/test split across all available months (`2024-01..2024-04`), or training on only a single month (`2024-03`).

## Why

Taxi demand, traffic patterns, and trip durations are temporal time-series processes subject to seasonal drift, holiday shifts, and evolving city construction. A random train/test split would leak future temporal correlation and same-day traffic conditions into the training set, yielding artificially optimistic evaluation metrics. Evaluating on the chronologically subsequent month (`2024-04`) accurately mirrors production inference, where models predict future trips using past data. Computing the distance lookup strictly from `2024-01..2024-03` prevents target and lookahead leakage. A 3-month window (~9.55M trips) provides sufficient coverage of rare zone pairs while remaining well within the memory and compute capacity of the `t4g.large` host.

## What would show this was wrong

If significant seasonal drift (e.g. winter vs. summer traffic patterns) renders a rolling 3-month window unrepresentative, or if data volume growth makes 3-month training too slow, indicating a need for a dynamic decaying window or explicit seasonality features.
