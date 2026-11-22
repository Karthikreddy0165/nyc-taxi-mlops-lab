# 016: Vector index for pgvector (HNSW vs IVFFlat)

Stage: S6 · Date: 2026-11-22 · Author: karthik · Drafted by agent: yes

## Choice

Use an **HNSW (Hierarchical Navigable Small World)** index (`using hnsw (embedding vector_cosine_ops)`) on the `rag.chunks` table in RDS PostgreSQL.

## Rejected alternative

- **IVFFlat (Inverted File with Flat compression):** considered for lower memory usage and faster index construction.

## Why

1. **Immediate High Recall on Small & Growing Datasets:** Our wiki contains ~16 pages and dozens of chunks initially, updated daily via incremental ingestion. HNSW provides >99% recall immediately without requiring pre-training or cluster tuning.
2. **No Re-indexing Required on Updates:** IVFFlat requires training centroid lists (`lists` parameter) against an already populated dataset and suffers severe recall degradation as new vectors are added unless periodically rebuilt with `REINDEX`. HNSW smoothly handles incremental inserts and deletions as wiki pages are published or edited.
3. **Memory Overhead is Negligible:** On our RDS instance (`db.t4g.micro` / `medium`), storing an HNSW graph for hundreds or thousands of 768-dimensional vectors consumes only a few megabytes of RAM, well within our database allocation.

## What would show this was wrong

- If the knowledge base scaled to millions of chunks where HNSW index memory exceeded RDS RAM limits and slowed writes down, we would consider IVFFlat with partitioned clustering.
