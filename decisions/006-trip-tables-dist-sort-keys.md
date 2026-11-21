# 006: Distribution and sort keys for trip tables

Stage: S1 · Date: 2026-11-21 · Author: karthik · Drafted by agent: yes

## Choice

Use `SORTKEY (pickup_at)` for `staging.stg_trips` and rely on Redshift `DISTSTYLE AUTO` / `EVEN` for row distribution across slices.

## Rejected alternative

Distributing `stg_trips` by `DISTKEY (pickup_zone_id)`.

## Why

Almost all analytical queries, monthly partitioning, feature extraction windows, and aggregate mart calculations filter by time range (`pickup_at`). A sort key on `pickup_at` allows Redshift to leverage 1MB block zone maps to prune out 90%+ of disk blocks during range scans. For distribution, taxi trips exhibit extreme geographical skew (high trip volumes in Midtown Manhattan and JFK Airport vs. sparse trips in outer boroughs). Distributing on `pickup_zone_id` would concentrate huge data volumes and query execution onto a single slice, causing bottlenecking. `DISTSTYLE AUTO`/`EVEN` distributes rows evenly across all slices, maximizing parallel processing throughput.

## What would show this was wrong

If large distributed joins between `stg_trips` and another massive table sharing a join key caused network broadcast/redistribution bottlenecks that outweigh slice skew.
