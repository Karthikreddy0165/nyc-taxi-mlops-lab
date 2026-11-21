# 004: Ingestion mechanism: Redshift COPY vs Spectrum

Stage: S1 · Date: 2026-11-21 · Author: karthik · Drafted by agent: yes

## Choice

Load monthly NYC taxi Parquet files into Redshift managed storage using the Redshift `COPY` command.

## Rejected alternative

Querying the Parquet files in place in S3 via Redshift Spectrum external tables.

## Why

Our pipeline and downstream serving/feature-extraction workloads perform repeated aggregations, windowing, and percentile calculations (such as `zone_hour_stats`). Ingesting via `COPY` stores the data directly on Redshift local columnar storage, enabling 1MB block zone maps, local SSD caching, and predictable query latencies without S3 network overhead or per-query scan costs. Although `COPY` incurs an initial ingestion time and consumes cluster disk space, the data volume (~3 million rows per month) easily fits within cluster storage limits.

## What would show this was wrong

If monthly data volumes grew to tens of terabytes where cluster storage costs exceed budget, or if trip files were queried only once or twice for ad-hoc inspection rather than repeated model training and mart generation.
