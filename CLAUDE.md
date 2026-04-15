# Context8 — Collective Problem-Solving Memory for Coding Agents

## Project Overview

Context8 is an MCP server backed by Actian VectorAI DB that stores and retrieves coding problem-solution pairs. It complements Context7 (documentation search) by covering the long tail of uncommon errors, workarounds, and agent-discovered fixes that don't appear in official documentation.

## Tech Stack

- **Database:** Actian VectorAI DB (Docker, gRPC port 50051)
- **Language:** Python 3.10+
- **Embedding Models:** sentence-transformers/all-MiniLM-L6-v2 (384d), microsoft/codebert-base (768d)
- **Protocol:** MCP (Model Context Protocol) via stdio
- **SDK:** actian-vectorai Python client

## Project Structure

```
actian-hackathon/
├── CLAUDE.md                           # This file
├── docker-compose.yml                  # Actian VectorAI DB container
├── requirements.txt                    # Python dependencies
├── src/context8/
│   ├── __init__.py
│   ├── __main__.py                     # CLI entry point
│   ├── server.py                       # MCP server
│   ├── models.py                       # Data models (ResolutionRecord)
│   ├── storage.py                      # Actian VectorAI DB operations
│   ├── embeddings.py                   # Embedding pipeline
│   ├── search.py                       # Hybrid search engine
│   ├── seed.py                         # Starter data
│   └── config.py                       # Constants
├── tests/
│   ├── conftest.py
│   ├── test_models.py
│   ├── test_embeddings.py
│   ├── test_storage_integration.py
│   ├── test_search_integration.py
│   ├── test_ground_truth.py
│   └── test_e2e.py
├── scripts/
│   ├── verify_connection.py
│   ├── start.sh
│   └── start.ps1
└── docs/                               # Comprehensive documentation
    ├── CONCEPT.md                      # Vision and motivation
    ├── ARCHITECTURE.md                 # System architecture
    ├── PLAN-01-INFRASTRUCTURE.md       # Docker + DB setup
    ├── PLAN-02-EMBEDDING-PIPELINE.md   # Embedding models
    ├── PLAN-03-STORAGE-SCHEMA.md       # Collection design
    ├── PLAN-04-MCP-SERVER.md           # MCP server
    ├── PLAN-05-SEARCH-ENGINE.md        # Hybrid search
    ├── PLAN-06-AGENT-INTEGRATION.md    # Agent integration
    ├── PLAN-07-COLD-START.md           # Cold start + seeding
    ├── PLAN-08-TESTING.md              # Testing strategy
    └── BOTTLENECKS.md                  # Risks and mitigations
```

## Key Design Decisions

1. **Three named vector spaces** (problem/solution/code_context) — different semantic domains need different representations
2. **Hybrid search** (dense + sparse + RRF fusion) — error messages need both semantic AND keyword matching
3. **MiniLM default, CodeBERT opt-in** — keep memory footprint reasonable by default
4. **Deduplication at log time** — prevent the same problem from creating hundreds of records
5. **Curated seed dataset** — solve cold start with 60+ real-world problem-solution pairs

## Commands

```bash
docker compose up -d                    # Start database
python -m context8 --init               # Initialize collection
python -m context8 --seed               # Seed with starter data
python -m context8 --stats              # Show stats
python -m context8                      # Start MCP server
pytest tests/ -v                        # Run all tests
```

## Coding Conventions

- Python 3.10+ with type hints everywhere
- Dataclasses for data models (not Pydantic, keep deps light)
- `from __future__ import annotations` in every file
- Sync client for simplicity, async where concurrency matters
- Tests use pytest with pytest-asyncio for async tests
- All Actian VectorAI DB operations go through StorageService (never raw client calls in server.py)

## Actian VectorAI DB Notes

- gRPC on port 50051 (primary), REST on 50052 (fallback)
- `create_field_index()` is UNIMPLEMENTED on server — use default indexing
- Sparse-only collections may not work — always use hybrid (dense + sparse)
- `set_payload()`/`delete_payload()` may not work — use delete + re-upsert pattern
- Collection name: `context8_store`
- Use `VectorAIClient` context manager (`with` statement) to ensure cleanup
