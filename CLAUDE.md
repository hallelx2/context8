# Context8 — Collective Problem-Solving Memory for Coding Agents

## Project Overview

Context8 is an MCP server that stores and retrieves coding problem-solution pairs in a local SQLite database (with sqlite-vec for vector search and FTS5 for BM25 keyword search). It complements Context7 (documentation search) by covering the long tail of uncommon errors, workarounds, and agent-discovered fixes that don't appear in official documentation.

The original hackathon submission ran on Actian VectorAI DB over gRPC. That backend is still supported — install the SDK wheel from GitHub alongside `context8` and set `CONTEXT8_BACKEND=actian` — but it is no longer the default. (PyPI doesn't allow URL-pinned extras, so we can't ship an `[actian]` extra; the wheel install stays manual until the SDK lands on PyPI.)

## Tech Stack

- **Default storage:** SQLite (stdlib) + [sqlite-vec](https://github.com/asg017/sqlite-vec) for vec0 KNN + native FTS5 for BM25. Single file at `~/.context8/context8.db`.
- **Optional storage:** Actian VectorAI DB over gRPC. Install: `pip install "actian-vectorai @ https://github.com/hackmamba-io/actian-vectorAI-db-beta/raw/main/actian_vectorai-0.1.0b2-py3-none-any.whl"` then set `CONTEXT8_BACKEND=actian`.
- **Language:** Python 3.10+
- **Embedding models:** `sentence-transformers/all-MiniLM-L6-v2` (384d default); `microsoft/codebert-base` (768d, opt-in via `CONTEXT8_USE_CODE_MODEL=1`).
- **Protocol:** MCP (Model Context Protocol) via stdio.

## Project Structure

```
actian-hackathon/
├── CLAUDE.md                           # This file
├── README.md
├── RESULTS.md                          # Submission deliverable: bench numbers + narrative
├── pyproject.toml
├── docker-compose.yml                  # Actian VectorAI DB container (used only under [actian])
├── src/context8/
│   ├── __init__.py
│   ├── __main__.py                     # python -m context8 → CLI entry
│   ├── config.py                       # Env-driven backend resolution + paths
│   ├── models.py                       # ResolutionRecord, FeedbackStats, SearchResult
│   ├── storage/                        # Pluggable storage package
│   │   ├── backend.py                  # StorageBackend Protocol + SearchFilter + ScoredHit
│   │   ├── sqlite_schema.py            # DDL + apply_migrations + dim guard
│   │   ├── sqlite_backend.py           # SQLite + sqlite-vec + FTS5 (default)
│   │   ├── actian_backend.py           # Actian VectorAI DB (legacy, optional)
│   │   └── service.py                  # StorageService env-driven facade
│   ├── docker.py                       # Container helpers (Actian only — guards no-op for SQLite)
│   ├── feedback.py                     # FeedbackService — agent rate-this-fix loop
│   ├── browse.py                       # Metadata-only browsing (no vector query)
│   ├── export.py                       # Backend-agnostic JSON export/import
│   ├── agents.py                       # Editor MCP config writer
│   ├── embeddings/
│   │   ├── service.py                  # MiniLM + CodeBERT lazy loaders
│   │   └── tokenizer.py                # BM25 tokenizer (used by ActianBackend.search_sparse)
│   ├── search/
│   │   ├── engine.py                   # Backend-agnostic hybrid search
│   │   ├── fusion.py                   # Pure-Python Reciprocal Rank Fusion
│   │   ├── analyzer.py                 # QueryAnalyzer (per-query weight tuning)
│   │   ├── ranking.py                  # Confidence + recency + worked-ratio ranker
│   │   └── attribution.py              # Per-strategy score tracking
│   ├── ingest/
│   │   ├── pipeline.py                 # Generic batched ingest pipeline
│   │   ├── seed.py                     # 23 curated problem-solution starter records
│   │   ├── github.py                   # GitHub Issues importer
│   │   └── sessions.py                 # Claude Code session miner
│   ├── benchmark/
│   │   ├── ground_truth.py             # 27 query→record evaluation pairs
│   │   └── runner.py                   # Recall@K / MRR / latency evaluator
│   ├── mcp/
│   │   ├── server.py                   # MCP server entry point
│   │   ├── tools.py                    # MCP tool dispatch
│   │   └── tools_browse.py             # Browse / ecosystem MCP tools
│   ├── hooks/                          # Claude Code hook helpers (capture/suggest)
│   └── cli/
│       ├── main.py                     # Click group entry
│       ├── ui.py                       # Rich helpers + backend-aware health checks
│       └── commands/
│           ├── lifecycle.py            # start / stop / init (backend-aware)
│           ├── ops.py                  # stats / doctor / search / browse / export / import
│           ├── integrations.py         # add / remove (editor configs)
│           ├── bench.py                # bench / demo
│           ├── ingest.py               # import-github / mine
│           └── serve.py                # serve (MCP, backend-aware bootstrap)
├── tests/
│   ├── test_models.py
│   ├── test_models_extended.py
│   ├── test_embeddings.py
│   ├── test_attribution.py
│   ├── test_ranking.py
│   ├── test_benchmark.py
│   ├── test_github_importer.py
│   ├── test_agents.py
│   ├── test_search_filter.py           # NEW — SearchFilter → SQL/FilterBuilder translation
│   ├── test_storage_sqlite.py          # NEW — SQLiteBackend unit tests
│   ├── test_e2e_sqlite.py              # NEW — full e2e against SQLite (no Docker)
│   └── test_e2e.py                     # Legacy Actian e2e — gated by CONTEXT8_BACKEND=actian
├── scripts/
│   ├── verify_connection.py
│   ├── start.sh
│   └── start.ps1
└── docs/                               # Hackathon-era design docs (banner says historical)
    ├── CONCEPT.md
    ├── ARCHITECTURE.md
    ├── BOTTLENECKS.md
    ├── PLAN-01..08-*.md
    └── Hackathon Demo Video — Script.md
```

## Key Design Decisions

1. **Pluggable storage backend (`StorageBackend` Protocol).** Default = SQLite + sqlite-vec + FTS5 (zero infrastructure). Optional = Actian VectorAI DB. The engine, ingest, and MCP layers never import a vendor SDK.
2. **Three named vector spaces** (problem/solution/code_context) — different semantic domains need different representations.
3. **Hybrid search** (dense vec0 + FTS5 BM25 + RRF fusion in Python) — error messages need both semantic AND keyword matching.
4. **MiniLM 384d default, CodeBERT 768d opt-in.** vec0 dim is fixed at `CREATE VIRTUAL TABLE` time; flipping `CONTEXT8_USE_CODE_MODEL` after init fails loudly with a `--force` hint.
5. **Deduplication at log time.** Prevent the same problem from creating hundreds of records.
6. **Curated seed dataset.** Solve cold start with 23 real-world problem-solution pairs.
7. **WAL mode + 5s busy timeout.** MCP read concurrency is unrestricted; writers (CLI ingest, MCP `_handle_log`) serialize.

## Commands

```bash
# Default (SQLite — no daemon needed)
pip install context8
context8 init --seed                    # creates ~/.context8/context8.db, seeds 23 records
context8 add claude-code                # wire up MCP for Claude Code
context8 doctor                         # health check
context8 stats                          # record count, vector spaces, hybrid status
context8 search "ModuleNotFoundError cv2"
context8 bench                          # ablate features over the 27-query ground truth
pytest tests/ -v                        # ~127 tests (Actian e2e auto-skips)

# Optional Actian backend
pip install "actian-vectorai @ https://github.com/hackmamba-io/actian-vectorAI-db-beta/raw/main/actian_vectorai-0.1.0b2-py3-none-any.whl"
docker compose up -d
CONTEXT8_BACKEND=actian context8 init --seed
CONTEXT8_BACKEND=actian context8 doctor
CONTEXT8_BACKEND=actian pytest tests/ -v
```

## Coding Conventions

- Python 3.10+ with type hints everywhere.
- Dataclasses for data models (not Pydantic, keep deps light).
- `from __future__ import annotations` in every file.
- Sync client for simplicity; async only where concurrency matters (MCP loop).
- Tests use pytest with pytest-asyncio (auto mode).
- **Never reach into a vendor SDK from outside `storage/<backend>_backend.py`.** All search/CRUD goes through the `StorageBackend` Protocol via `StorageService`.

## SQLite Backend Notes

- DB file: `~/.context8/context8.db` (override with `CONTEXT8_DB_PATH`).
- Three vec0 virtual tables: `vec_problem`, `vec_solution`, `vec_code_context`. All declared `distance=cosine` so scores match Actian semantics (`score = 1.0 - distance`).
- One FTS5 virtual table: `fts_records` with `tokenize='unicode61 remove_diacritics 2'`.
- One regular `records` table with B-tree indexes on `language`, `framework`, `error_type`, `source`, `resolved`, `last_seen`. `tags` and `libraries` are JSON1 arrays.
- WAL mode set on every connection by `apply_pragmas`. `busy_timeout=5000`.
- Schema version tracked in `schema_version` table; dim choices in `meta` table.
- `MCP serve` and `context8 ingest` must not run concurrently — sqlite-vec serializes writes (reads are unaffected).

## Actian Backend Notes (legacy)

- gRPC on port 50051 (primary), REST on 50052 (fallback).
- `create_field_index()` is UNIMPLEMENTED on server — use default indexing.
- Sparse-only collections may not work — always use hybrid (dense + sparse).
- `set_payload()`/`delete_payload()` may not work — use delete + re-upsert pattern.
- Collection name: `context8_store`.
- Use `VectorAIClient` context manager (`with` statement) to ensure cleanup.
