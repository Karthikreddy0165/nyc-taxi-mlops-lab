# 005: Data quality checks: blocking vs warning severity

Stage: S1 · Date: 2026-11-21 · Author: karthik · Drafted by agent: yes

## Choice

Enforce structural schema mismatches (`schema_contract` on `trip_files`) and unreasonable monthly row counts (`plausible_row_count` on `stg_trips`) as blocking checks (`ERROR`). Treat row-level value anomalies (`valid_timestamps`) as non-blocking checks (`WARN`).

## Rejected alternative

A strict policy where any single row anomaly (e.g., negative duration or out-of-range timestamp) blocks the entire pipeline, or a permissive policy where all checks only warn.

## Why

Redshift's Parquet `COPY` command maps columns strictly by position, not by name. A schema drift (renamed, added, or reordered column) causes silent data corruption or fatal COPY errors; thus schema validation must block before ingestion. Similarly, an empty or truncated file indicates an upstream ingestion failure and must block mart materialization. However, real-world TLC taxi data contains dirty rows (e.g. meter errors or negative durations) that staging tables should retain for data scientists to inspect and filter during feature engineering (`trip_features`) rather than stalling the entire pipeline overnight.

## What would show this was wrong

If dirty rows in staging silently contaminated the final `marts.zone_hour_stats` aggregates or model training features, requiring stricter blocking gates earlier in the pipeline.
