# 008: Promotion metric, winning margin, and latency budget

Stage: S2 · Date: 2026-11-21 · Author: karthik · Drafted by agent: yes

## Choice

Use Mean Absolute Error (`mae_min`) on the holdout month (`2024-04`) as the primary promotion metric. To qualify for the `challenger` alias, a candidate model must beat the current champion (or the v1 baseline if no champion exists) by at least 0.10 minutes (6 seconds) lower MAE (`candidate_mae <= champion_mae - 0.10`), while maintaining a single-row p95 inference latency $\le$ 10.0 milliseconds.

## Rejected alternative

Promoting on any strict MAE improvement with zero margin (`candidate_mae < champion_mae`), or using Root Mean Squared Error (RMSE) instead of MAE.

## Why

In trip duration prediction, TLC records contain extreme tail trips (e.g. 2-3 hour congestion delays or detours). RMSE squares errors, disproportionately penalizing outliers and biasing models towards over-predicting typical trips. MAE rewards median accuracy and represents the true expected error riders experience. Furthermore, requiring an absolute winning margin of 0.10 minutes (6 seconds) prevents "alias churn", where models get promoted due to minor random evaluation noise rather than meaningful algorithmic superiority. The 10 ms p95 latency budget ensures the candidate model can comfortably meet real-time serving SLAs.

## What would show this was wrong

If production latency spikes under high concurrent load despite passing the 10 ms single-row benchmark, or if a model achieves the 0.10 min overall MAE improvement while severely degrading accuracy on key business slices like airport trips or Manhattan rush hours.
