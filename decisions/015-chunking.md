# 015: Chunk size, overlap, and top-k for support assistant RAG

Stage: S6 · Date: 2026-11-22 · Author: karthik · Drafted by agent: yes

## Choice

Chunk ops wiki markdown pages with `max_tokens = 300` and `overlap_tokens = 40`, and retrieve `top_k = 3` chunks via cosine similarity for grounding answers in `POST /assist`.

## Rejected alternative

- Granular chunks (`max_tokens = 150`, `overlap_tokens = 20`, `top_k = 4-5`): considered for higher embedding precision per chunk.
- Large chunks (`max_tokens = 500`, `overlap_tokens = 50`, `top_k = 2`): considered for maximizing section context per retrieval.

## Why

1. **Section Coherence:** Ops wiki pages are relatively concise policy documents (e.g., surcharge tables, dispatch rules, airport buffers). A chunk size of 300 tokens (approx. 230 words) cleanly encompasses 1–2 complete markdown subsections along with their parent heading hierarchy, ensuring rules and numerical tables are not severed across chunks.
2. **LLM Prompt Reading Latency on CPU:** The LLM host runs Qwen3-4B on an ARM64 CPU (`m8g.large`), which reads prompt tokens at ~13 tokens/second. Retrieving 3 chunks of ~200–250 tokens adds ~700 prompt tokens (~50s of generation and prompt evaluation time). Setting `top_k = 3` keeps total request turnaround comfortably within the 120s–150s HTTP timeout while providing adequate grounding across multiple policies.
3. **Overlap:** A 40-token overlap prevents boundary loss across paragraph transitions without incurring redundant embedding cost.

## What would show this was wrong

- Rider questions frequently failing to retrieve relevant surcharge amounts or policies because the necessary details were split across adjacent chunks would indicate `max_tokens` is too small.
- Request timeouts exceeding 120s on multi-chunk retrievals or high prompt evaluation latency would indicate `top_k` or chunk size needs reduction.
