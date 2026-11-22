"""S6: the wiki RAG branch, in the `rag` database on RDS (pgvector), on a daily schedule.

- wiki_pages: the published pages from the ops wiki (resource `wiki`: labpipes/wiki.py). Store each
  page's ETag and send it next time: an unchanged page then costs a 304 and no body.
- wiki_chunks: split changed pages with labpipes.chunking.chunk_markdown (chunk size and overlap are
  decision 015) and store the chunks; use Chunk.content_hash as the id so unchanged text keeps it.
- wiki_embeddings: embed only the chunks that have no vector yet (resource `embed`: nomic-embed-text,
  768 dimensions) and store them as pgvector `vector(768)`, with an index (HNSW: decision 016).
- A blocking check that every chunk has a vector, and a schedule (and a job you can run by hand with
  scripts/dagster-run.sh) for the three.
"""

import dagster as dg

from labpipes.chunking import chunk_markdown
from labpipes.resources import LlmEmbed, RagStore, WikiApi

MAX_TOKENS = 300  # decision 015
OVERLAP_TOKENS = 40  # decision 015


@dg.asset(group_name="rag", compute_kind="python")
def wiki_pages(context: dg.AssetExecutionContext, wiki: WikiApi, rag: RagStore) -> dg.MaterializeResult:
    """Fetch pages from the ops wiki, sending ETags to avoid re-downloading unchanged pages (304)."""
    with rag.connect() as conn:
        with conn.cursor() as cur:
            cur.execute("create extension if not exists vector;")
            cur.execute("create schema if not exists rag;")
            cur.execute("""
                create table if not exists rag.pages (
                    id varchar(64) primary key,
                    title text not null,
                    updated_at text not null,
                    etag text not null,
                    body text not null,
                    fetched_at timestamp with time zone default now()
                );
            """)
            cur.execute("select id, etag from rag.pages;")
            stored_etags = dict(cur.fetchall())
        conn.commit()

    client = wiki.client()
    published_refs = client.pages()
    published_ids = [ref.id for ref in published_refs]

    fetched_pages = []
    unchanged_count = 0

    for ref in published_refs:
        etag = stored_etags.get(ref.id)
        page = client.page(ref.id, etag=etag)
        if page is None:
            unchanged_count += 1
        else:
            fetched_pages.append(page)

    with rag.connect() as conn:
        with conn.cursor() as cur:
            for p in fetched_pages:
                cur.execute(
                    """
                    insert into rag.pages (id, title, updated_at, etag, body, fetched_at)
                    values (%s, %s, %s, %s, %s, now())
                    on conflict (id) do update set
                        title = excluded.title,
                        updated_at = excluded.updated_at,
                        etag = excluded.etag,
                        body = excluded.body,
                        fetched_at = now();
                    """,
                    (p.id, p.title, p.updated_at, p.etag, p.body),
                )
            if published_ids:
                cur.execute("delete from rag.pages where not (id = any(%s));", (published_ids,))
        conn.commit()

    context.log.info(
        f"Checked {len(published_refs)} pages: {len(fetched_pages)} fetched (200), "
        f"{unchanged_count} unchanged (304)"
    )

    return dg.MaterializeResult(
        metadata={
            "pages_total": dg.MetadataValue.int(len(published_refs)),
            "pages_fetched": dg.MetadataValue.int(len(fetched_pages)),
            "pages_unchanged": dg.MetadataValue.int(unchanged_count),
        }
    )


@dg.asset(deps=[wiki_pages], group_name="rag", compute_kind="python")
def wiki_chunks(context: dg.AssetExecutionContext, rag: RagStore) -> dg.MaterializeResult:
    """Split wiki pages into content-hashed chunks (decision 015: max 300 tokens, 40 overlap)."""
    with rag.connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                create table if not exists rag.chunks (
                    id varchar(64) primary key,
                    page_id varchar(64) not null references rag.pages(id) on delete cascade,
                    chunk_index integer not null,
                    heading text not null,
                    text text not null,
                    tokens integer not null,
                    embedding vector(768)
                );
                create index if not exists chunks_page_id_idx on rag.chunks(page_id);
            """)
            cur.execute("select id, title, body from rag.pages order by id;")
            pages = cur.fetchall()
            cur.execute("select id from rag.chunks;")
            existing_chunk_ids = {row[0] for row in cur.fetchall()}
        conn.commit()

    total_chunks = 0
    new_chunks = 0
    all_current_chunk_ids = []

    with rag.connect() as conn:
        with conn.cursor() as cur:
            for page_id, title, body in pages:
                chunks = chunk_markdown(title, body, max_tokens=MAX_TOKENS, overlap_tokens=OVERLAP_TOKENS)
                page_chunk_ids = []
                for c in chunks:
                    chunk_id = c.content_hash(page_id)
                    page_chunk_ids.append(chunk_id)
                    all_current_chunk_ids.append(chunk_id)
                    total_chunks += 1
                    if chunk_id not in existing_chunk_ids:
                        new_chunks += 1
                    cur.execute(
                        """
                        insert into rag.chunks (id, page_id, chunk_index, heading, text, tokens)
                        values (%s, %s, %s, %s, %s, %s)
                        on conflict (id) do update set
                            chunk_index = excluded.chunk_index,
                            heading = excluded.heading,
                            tokens = excluded.tokens;
                        """,
                        (chunk_id, page_id, c.index, c.heading, c.text, c.tokens),
                    )
                if page_chunk_ids:
                    cur.execute("delete from rag.chunks where page_id = %s and not (id = any(%s));", (page_id, page_chunk_ids))
            if all_current_chunk_ids:
                cur.execute("delete from rag.chunks where not (id = any(%s));", (all_current_chunk_ids,))
        conn.commit()

    context.log.info(f"Processed chunks: {total_chunks} total, {new_chunks} new")

    return dg.MaterializeResult(
        metadata={
            "chunks_total": dg.MetadataValue.int(total_chunks),
            "chunks_new": dg.MetadataValue.int(new_chunks),
        }
    )


@dg.asset(deps=[wiki_chunks], group_name="rag", compute_kind="python")
def wiki_embeddings(context: dg.AssetExecutionContext, embed: LlmEmbed, rag: RagStore) -> dg.MaterializeResult:
    """Generate 768-d embeddings for chunks lacking vectors and maintain HNSW index (decision 016)."""
    with rag.connect() as conn:
        with conn.cursor() as cur:
            cur.execute("select id, text from rag.chunks where embedding is null order by page_id, chunk_index;")
            unembedded = cur.fetchall()
        conn.commit()

    embedded_count = len(unembedded)
    if unembedded:
        context.log.info(f"Embedding {embedded_count} chunks with {embed.llm_host}...")
        texts = [row[1] for row in unembedded]
        vectors = embed.embed_documents(texts)

        with rag.connect() as conn:
            with conn.cursor() as cur:
                for (chunk_id, _), vec in zip(unembedded, vectors, strict=True):
                    vec_str = "[" + ",".join(f"{x:.7g}" for x in vec) + "]"
                    cur.execute("update rag.chunks set embedding = %s::vector where id = %s;", (vec_str, chunk_id))
                # Decision 016: HNSW index on cosine distance
                cur.execute("""
                    create index if not exists chunks_embedding_hnsw_idx
                    on rag.chunks using hnsw (embedding vector_cosine_ops);
                """)
            conn.commit()

    with rag.connect() as conn:
        with conn.cursor() as cur:
            cur.execute("select count(*) from rag.chunks where embedding is not null;")
            total_embedded = cur.fetchone()[0]
        conn.commit()

    return dg.MaterializeResult(
        metadata={
            "chunks_embedded": dg.MetadataValue.int(embedded_count),
            "total_embedded": dg.MetadataValue.int(total_embedded),
        }
    )


@dg.asset_check(asset=wiki_embeddings, blocking=True, description="Every chunk in rag.chunks has an embedding vector.")
def every_chunk_has_vector(context: dg.AssetCheckExecutionContext, rag: RagStore) -> dg.AssetCheckResult:
    """Blocking check: fails if any chunk is missing an embedding vector."""
    with rag.connect() as conn:
        with conn.cursor() as cur:
            cur.execute("select count(*) from rag.chunks where embedding is null;")
            missing = cur.fetchone()[0]

    return dg.AssetCheckResult(
        passed=(missing == 0),
        severity=dg.AssetCheckSeverity.ERROR,
        description=f"{missing} chunk(s) missing embeddings",
        metadata={"missing_chunks": dg.MetadataValue.int(missing)},
    )


ingest_wiki = dg.define_asset_job(
    "ingest_wiki",
    selection=dg.AssetSelection.assets(wiki_pages, wiki_chunks, wiki_embeddings)
    | dg.AssetSelection.checks(every_chunk_has_vector),
)

daily_wiki_schedule = dg.ScheduleDefinition(
    job=ingest_wiki,
    cron_schedule="0 0 * * *",
)
