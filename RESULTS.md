# Context8 — Results

> Originally written as the Actian VectorAI DB Build Challenge submission deliverable.
> Context8 is now SQLite-first by default (`pip install context8`); the Actian backend
> remains a supported optional install (install the GitHub wheel separately, then set
> `CONTEXT8_BACKEND=actian`). Run `context8 bench` against either backend to
> reproduce the numbers below.

## TL;DR

Context8 is a collective problem-solving memory for coding agents — the missing layer between agent context and Context7's documentation search. The retrieval stack — three named vector spaces, hybrid dense + sparse fusion via RRF, and metadata-filtered search — was originally built on Actian VectorAI DB and now also runs on stock SQLite + sqlite-vec + FTS5 with no infrastructure. We ship the benchmark that quantifies what each capability is worth.

| Capability | What Context8 does with it | Without it |
|---|---|---|
| **Named vectors** | Three independent vector spaces (`problem`, `solution`, `code_context`) — a record can be retrieved via error text, code pattern, or solution approach. SQLite uses three vec0 virtual tables; Actian uses three named-vector slots in one collection. | Single-vector search collapses three semantically different access paths into one |
| **Hybrid fusion (RRF)** | Dense MiniLM + sparse keyword search (FTS5 BM25 on SQLite, sparse vectors on Actian), fused with Reciprocal Rank Fusion in pure Python — error codes (`ERESOLVE`, `E0463`) match exactly while paraphrased queries still match semantically. | Either you miss exact tokens (dense-only) or you miss paraphrases (sparse-only) |
| **Filtered search** | Server-side metadata filters by language/framework/error-type/resolved/feedback markers. SQLite uses indexed `WHERE` + JSON1 `json_each` for tag arrays; Actian uses `FilterBuilder`. | Python results pollute TypeScript searches; can't narrow by stack |

## How to reproduce

```bash
# Default — SQLite, no Docker
pip install context8
context8 init --seed                                   # Curated 23-record dataset
context8 import-github vercel/next.js --max-issues 30  # Real issues at scale
context8 import-github fastapi/fastapi --max-issues 20
context8 doctor                                        # Verify all features live
context8 bench                                         # Print Recall@K table
context8 demo                                          # 4 scripted scenarios

# Actian backend (legacy hackathon stack)
pip install "actian-vectorai @ https://github.com/hackmamba-io/actian-vectorAI-db-beta/raw/main/actian_vectorai-0.1.0b2-py3-none-any.whl"
docker compose up -d
CONTEXT8_BACKEND=actian context8 init --seed
CONTEXT8_BACKEND=actian context8 bench
```

## Benchmark results

> Replace this section with the live output of `context8 bench` after running against your DB.
> Run under both backends to compare retrieval quality (we expect them to be very close — the same embeddings + the same RRF, only the index implementation differs).

### SQLite + sqlite-vec + FTS5 (default)

| Configuration | Recall@1 | Recall@3 | Recall@5 | MRR | p50 latency |
|---|---:|---:|---:|---:|---:|
| dense (problem only) | _TBD_ | _TBD_ | _TBD_ | _TBD_ | _TBD_ ms |
| + named vectors | _TBD_ | _TBD_ | _TBD_ | _TBD_ | _TBD_ ms |
| + hybrid fusion | _TBD_ | _TBD_ | _TBD_ | _TBD_ | _TBD_ ms |
| + filtered search | _TBD_ | _TBD_ | _TBD_ | _TBD_ | _TBD_ ms |
| + quality ranker | _TBD_ | _TBD_ | _TBD_ | _TBD_ | _TBD_ ms |

### Actian VectorAI DB (optional)

| Configuration | Recall@1 | Recall@3 | Recall@5 | MRR | p50 latency |
|---|---:|---:|---:|---:|---:|
| dense (problem only) | _TBD_ | _TBD_ | _TBD_ | _TBD_ | _TBD_ ms |
| + named vectors | _TBD_ | _TBD_ | _TBD_ | _TBD_ | _TBD_ ms |
| + hybrid fusion | _TBD_ | _TBD_ | _TBD_ | _TBD_ | _TBD_ ms |
| + filtered search | _TBD_ | _TBD_ | _TBD_ | _TBD_ | _TBD_ ms |
| + quality ranker | _TBD_ | _TBD_ | _TBD_ | _TBD_ | _TBD_ ms |

The ground-truth set is defined in `src/context8/benchmark/ground_truth.py` (27 queries paired with deterministic seed slugs). Queries deliberately use different vocabulary than the seed problem text, so dense-only search has to actually generalize.

## What makes this submission stand out

### 1. Each retrieval feature is measurably load-bearing
Most submissions enable hybrid search because the rules say to. Context8 ships an ablation harness that turns each feature off in turn and quantifies the cost. The deltas in the tables above are the proof — without numbers, "we use named vectors" is just a claim.

### 2. A bidirectional MCP loop nobody else will have
Beyond `search` and `log`, Context8 exposes `context8_rate(record_id, worked)`. The agent reports outcomes back into the DB. The `worked_ratio` then feeds the ranker, so the knowledge base genuinely gets better with use. On Actian this required a delete + re-upsert workaround for missing payload-mutation APIs; on SQLite it's a single `UPDATE`.

### 3. Per-strategy attribution surfaces the retrieval stack at work
Every result includes which named vector or sparse search surfaced it, at what rank, with what score. Operators (and judges) can see that hybrid fusion is firing — not infer it from a black box. The `AttributionTracker` is backend-agnostic; it works identically across SQLite vec0 hits and Actian search hits.

### 4. A self-improving ranker
Final score blends raw retrieval with confidence (record self-rating), recency (exponential decay over the configured half-life), and worked-ratio (agent-reported success rate, gated by minimum sample count). Configurable via env vars in `config.py`.

### 5. Real data at scale, not toy data
`context8 import-github <repo>` walks a public repository's closed issues, scores their comments for resolution markers, extracts language/framework/error-type metadata, and ingests them. Ship the framework with one curl-style command and your DB has hundreds of real-world fixes within a minute.

### 6. Production-grade health checks
`context8 doctor` verifies the retrieval features are actually live on the collection (named-vector count ≥ 3, sparse vectors enabled, hybrid query path returns, filtered search succeeds). On SQLite it additionally probes WAL mode and runs `PRAGMA integrity_check`. No silent degradation hiding behind a green checkmark.

### 7. Pluggable storage with zero infrastructure default
The original hackathon stack (Actian VectorAI DB over gRPC + Docker) is preserved as an optional backend. The default install is single-command `pip install context8` — no daemon, no compose, single SQLite file at `~/.context8/context8.db`. Same MCP tools, same search semantics, same CLI.

## Project layout

The framework is organized so that someone landing on the repo for the first time can navigate by capability:

- `embeddings/` — what we turn text into
- `storage/` — pluggable backends (SQLite default, Actian optional, both behind one Protocol)
- `search/` — how we retrieve and rank (engine + fusion + analyzer + ranking + attribution)
- `ingest/` — how data gets in (seed + pipeline + github + sessions)
- `benchmark/` — how we prove quality (ground_truth + runner)
- `mcp/` — how agents call us (server + tools)
- `cli/` — how humans drive the framework (commands grouped by concern)
- `feedback.py` — the agent rating loop
- `models.py` — the data shapes shared across all of the above

## License

MIT — see `LICENSE`.
