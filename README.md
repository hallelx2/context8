<p align="center">
  <img src="https://img.shields.io/badge/Context8-Agent%20Memory-blueviolet?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCI+PHBhdGggZD0iTTEyIDJhMTAgMTAgMCAxIDAgMCAyMCAxMCAxMCAwIDAgMCAwLTIweiIvPjxwYXRoIGQ9Ik0xMiA2djEyIi8+PHBhdGggZD0iTTYgMTJoMTIiLz48L3N2Zz4=" alt="Context8">
</p>

<h1 align="center">Context8</h1>

<p align="center">
  <strong>Collective problem-solving memory for coding agents</strong><br>
  <em>Local-first by default — SQLite + sqlite-vec. No daemon. No Docker.</em>
</p>

<p align="center">
  <a href="https://pypi.org/project/context8/"><img src="https://img.shields.io/pypi/v/context8?style=flat-square&color=blue" alt="PyPI"></a>
  <a href="https://pypi.org/project/context8/"><img src="https://img.shields.io/pypi/pyversions/context8?style=flat-square" alt="Python"></a>
  <a href="https://github.com/hallelx2/context8/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/hallelx2/context8/ci.yml?branch=main&style=flat-square&label=CI" alt="CI"></a>
  <a href="https://github.com/hallelx2/context8/blob/main/LICENSE"><img src="https://img.shields.io/github/license/hallelx2/context8?style=flat-square" alt="License"></a>
  <a href="https://github.com/hallelx2/context8/releases"><img src="https://img.shields.io/github/v/release/hallelx2/context8?style=flat-square&color=green" alt="Release"></a>
  <a href="https://github.com/hallelx2/context8"><img src="https://img.shields.io/github/stars/hallelx2/context8?style=flat-square" alt="Stars"></a>
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> •
  <a href="#how-it-works">How It Works</a> •
  <a href="#context8-vs-context7-vs-skills">Comparison</a> •
  <a href="#cli-reference">CLI</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#development">Development</a>
</p>

---

Context7 gives your agent the docs. **Context8 gives it what the docs don't cover.**

Every time a coding agent solves an uncommon error, the solution vanishes after the session. Context8 stores those solutions in a vector database so any agent — yours or your team's — can find them next time.

```
Agent hits error → searches Context8 → finds a past solution → applies it
                                            ↓
                     Agent solves new error → logs it to Context8 → future agents benefit
```

---

## Prerequisites

| Requirement | Why |
|---|---|
| Python 3.10+ | Runs the Context8 CLI and MCP server. SQLite ships with stdlib; `sqlite-vec` and FTS5 do the rest. |

That's it — no Docker, no daemon, no separate database to install.

## Quick Start

```bash
# 1. Install Context8
pip install context8

# 2. Initialize the local DB and seed with 23 curated problem-solution pairs
context8 init --seed

# 3. Wire up your coding agent (pick one)
context8 add claude-code   # Claude Code
context8 add cursor        # Cursor
context8 add windsurf      # Windsurf

# 4. Verify everything works
context8 doctor
```

Restart your agent. It now has these MCP tools: **`context8_search`**, **`context8_log`**, **`context8_rate`**, **`context8_search_solutions`**, **`context8_stats`**.

The DB lives at `~/.context8/context8.db` — a single SQLite file with three named vector spaces (`problem`, `solution`, `code_context`) backed by [sqlite-vec](https://github.com/asg017/sqlite-vec) and an FTS5 BM25 index for keyword search.

### Optional: Actian VectorAI DB backend

The original hackathon submission used Actian VectorAI DB over gRPC. That stack is still supported as an optional backend:

```bash
pip install "context8[actian]"
docker compose up -d                       # starts the Actian container
CONTEXT8_BACKEND=actian context8 init --seed
CONTEXT8_BACKEND=actian context8 doctor
```

Set `CONTEXT8_BACKEND=actian` (or leave unset for the default `sqlite`). The same MCP tools, search semantics, and CLI commands work across both backends.

---

## Context8 vs Context7 vs Skills

Coding agents have multiple ways to get help. Here's where each one fits and where it falls short:

### The Context Layers

| Layer | Source | What It Covers | Limits |
|---|---|---|---|
| **Context 1–6** | Codebase, conversation, memory | Your current project's files and history | Only knows *your* code |
| **Context7** | Official documentation (Upstash) | API references, common usage patterns, getting-started guides | Only covers *documented* knowledge |
| **Skills / CLAUDE.md** | Hand-written rules | Project conventions, tool-specific patterns, coding style | Manual maintenance, doesn't learn |
| **Context8** | Agent problem-solving history (local SQLite + sqlite-vec) | Uncommon errors, workarounds, integration bugs, agent-discovered fixes | Needs seeding and accumulation |

### When Each One Helps (and When It Doesn't)

| Scenario | Context7 (Docs) | Skills / Rules | Context8 (Memory) |
|---|---|---|---|
| "How do I use the `useQuery` hook?" | **Best fit** — it's in the React Query docs | Partial — if someone wrote a skill for it | Overkill — docs cover this |
| "What's our team's folder naming convention?" | Won't help — not in public docs | **Best fit** — written in CLAUDE.md | Won't help — not a problem/solution |
| `ERESOLVE unable to resolve dependency tree` after upgrading npm | Partial — npm docs mention peer deps vaguely | Won't help — too specific | **Best fit** — exact error with proven fix |
| Hydration mismatch in Next.js 15 + React 19 RC | Outdated — docs haven't caught up | Won't help | **Best fit** — another agent hit this last week |
| `torch.cuda.OutOfMemoryError` during fine-tuning even with batch_size=1 | Partial — PyTorch docs cover CUDA basics | Won't help | **Best fit** — solution with 4 ranked fix strategies |
| `docker compose` volume empty on Windows WSL2 | Won't help — Docker docs assume Linux | Maybe — if someone added a WSL tip | **Best fit** — exact OS-specific workaround |

### The Key Difference

```
Context7:  "Here's what the library author wrote in the docs"
Skills:    "Here's what a human wrote as a rule for this project"
Context8:  "Here's what an agent actually did to fix this exact problem last Tuesday"
```

**Context7** is a librarian — it finds the official answer.
**Skills** are a style guide — they enforce conventions.
**Context8** is a colleague — it remembers what worked in practice.

They're complementary. Use all three:

```
Agent encounters error
  ├── Check Skills/CLAUDE.md → "Do we have a rule for this?" (instant, project-specific)
  ├── Search Context7 → "What do the docs say?" (official, broad coverage)
  └── Search Context8 → "Has any agent solved this before?" (practical, battle-tested)
```

---

## How It Works

Context8 is an [MCP server](https://modelcontextprotocol.io/) backed by SQLite + sqlite-vec by default (Actian VectorAI DB optional). When your agent encounters an error:

1. **Search** — Agent calls `context8_search("TypeError Cannot read properties of undefined map React Suspense")`
2. **Match** — Context8 runs hybrid search: dense semantic vectors find meaning-similar problems, sparse keyword vectors catch exact error tokens, metadata filters narrow by language/framework
3. **Return** — Agent gets ranked solutions with code diffs, confidence scores, and context
4. **Learn** — After solving a new problem, the agent calls `context8_log(problem=..., solution=...)` to store it

### Three Search Strategies, Fused Together

| Strategy | Vector Space | What It Catches | Example |
|---|---|---|---|
| **Dense search** | `problem` (384d, MiniLM) | Semantic meaning | "undefined array access" matches "null reference on collection" |
| **Dense search** | `code_context` (384d default, 768d with `CONTEXT8_USE_CODE_MODEL=1` for CodeBERT) | Code patterns | `data?.items ?? []` matches `optional chaining null safety` |
| **Sparse search** | FTS5 BM25 (SQLite) or sparse keyword vectors (Actian) | Exact tokens | `ModuleNotFoundError` matches `ModuleNotFoundError` exactly |

Results are fused with **Reciprocal Rank Fusion (RRF)** and filtered by language, framework, and more. The `QueryAnalyzer` auto-detects query type and adjusts fusion weights:

| Query Type | Dense Weight | Code Weight | Sparse Weight |
|---|---|---|---|
| Error message (`TypeError: ...`) | 0.40 | 0.15 | **0.45** |
| Error + code context | 0.35 | 0.30 | 0.35 |
| Code snippet only | 0.25 | **0.55** | 0.20 |
| Natural language question | **0.60** | 0.15 | 0.25 |

---

## MCP Tools

Once connected, your agent has access to:

### `context8_search`

Search for past solutions to a problem.

```
Input:  query (required), code_context, language, framework, limit
Output: Ranked solutions with problem, fix, code diff, confidence, tags
```

### `context8_log`

Log a resolved problem for future agents.

```
Input:  problem (required), solution (required), error_type, code_snippet,
        code_diff, stack_trace, language, framework, libraries, tags, confidence
Output: Confirmation + record ID (or duplicate detection)
```

### `context8_stats`

Knowledge base health check.

```
Input:  (none)
Output: Record count, collection status, vector spaces, endpoint
```

---

## CLI Reference

### Setup

```bash
context8 init                   # Create the local DB (no daemon)
context8 init --seed            # Create + seed with starter data
context8 init --seed --force    # Drop, recreate, and reseed
context8 start                  # No-op for SQLite; starts container under [actian]
context8 stop                   # No-op for SQLite; stops container under [actian]
```

### Agent Integration

```bash
context8 add claude             # Add to Claude Code (~/.claude/settings.json)
context8 add claude-project     # Add to project-level Claude config
context8 add cursor             # Add to Cursor (.cursor/mcp.json)
context8 add windsurf           # Add to Windsurf (.windsurf/mcp.json)
context8 remove claude          # Remove from Claude Code
```

### Operations

```bash
context8 stats                          # Show knowledge base statistics
context8 doctor                         # Full health check (verifies named/sparse/hybrid/filter)
context8 search "query"                 # Search from the command line, with attribution
context8 search "query" -l python       # Search with language filter
context8 bench                          # Run retrieval benchmark, print Recall@K table
context8 demo                           # Scripted live demo of all advanced features
context8 import-github vercel/next.js   # Pull resolved issues from a GitHub repo
context8 serve                          # Start MCP server (agents call this automatically)
```

---

## What's in the box

Five capabilities that turn the basic "MCP + vector DB" pattern into a production-grade framework:

### 1. Real-world ingestion at scale

Beyond the 24-record curated seed, Context8 ships an importer that pulls resolved issues straight from GitHub:

```bash
context8 import-github vercel/next.js --label bug --max-issues 50
context8 import-github fastapi/fastapi --max-issues 30
context8 import-github huggingface/transformers --label bug --max-issues 30
```

The importer scans the closing comments for resolution markers (`fixed in`, `the fix is`, `workaround:` …), extracts language/framework/error-type signals from labels and repo names, and stores everything as Context8 records. One command, hundreds of real production fixes in your DB.

### 2. Agent feedback loop (`context8_rate`)

Context8 is bidirectional. After an agent applies a retrieved fix, it calls `context8_rate(record_id, worked=True)`. The record's `worked_count`/`applied_count` updates and feeds straight into the ranker — solutions that consistently work float to the top, ones that fail sink. This is the closed feedback loop that turns a static knowledge base into a self-improving one.

### 3. Per-strategy attribution

Every search result tells you exactly which Actian strategy surfaced it and at what rank:

```
Result 1 — score: 0.812 (raw: 0.945) — confidence: 95%
  via: keywords@1 (0.95) + problem@2 (0.78) + code_context@4 (0.61)
  boosts: confidence 1.00  recency 0.94  worked_ratio 0.92
  feedback: 7/8 worked (88%)
```

You can see the dense vector contributed less than the sparse keyword match, the recency factor barely penalized this record, and 8 prior agents have used this fix with 7 successes. The MCP tool returns the same attribution so agents can reason about result quality.

### 4. Quality ranker (`search/ranking.py`)

Final score = `retrieval × confidence_factor × recency_factor × worked_ratio_factor`. Each multiplier has a configurable floor (so a 0-confidence record loses at most 30%, never gets zeroed out), and feedback only kicks in once a record has been applied at least 3 times — preventing single bad ratings from sinking new solutions.

### 5. Evaluation as a first-class artifact

`context8 bench` ablates one Actian feature at a time over 27 ground-truth queries and prints a side-by-side table with green deltas. `context8 demo` runs four scripted scenarios (named vectors / hybrid fusion / filtered search / quality ranker) — designed as the script for a submission video.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              Coding Agent (Claude Code / Cursor / Windsurf)  │
└──────────────────────────┬──────────────────────────────────┘
                           │ MCP (stdio)
┌──────────────────────────▼──────────────────────────────────┐
│                   Context8 MCP Server                        │
│                                                              │
│  ┌────────────────┐  ┌───────────────┐  ┌────────────────┐  │
│  │   Embedding    │  │    Search     │  │ StorageService │  │
│  │   Pipeline     │  │    Engine     │  │   (facade)     │  │
│  │                │  │               │  │                │  │
│  │  MiniLM 384d   │  │  Dense+Sparse │  │  Pluggable     │  │
│  │  CodeBERT 768d │  │  RRF (Python) │  │  Backend       │  │
│  │  (opt-in)      │  │  QueryAnalyze │  │  Protocol      │  │
│  └────────────────┘  └───────────────┘  └────────┬───────┘  │
└────────────────────────────────────────────────────┼────────┘
                                                    │
        ┌───────────────────────┬───────────────────┘
        │                       │
        ▼ default               ▼ opt-in (CONTEXT8_BACKEND=actian)
┌─────────────────────────┐   ┌─────────────────────────┐
│  SQLiteBackend          │   │  ActianBackend          │
│  ~/.context8/context8.db│   │  Docker container :50051│
│                         │   │  (gRPC)                 │
│  • vec_problem  vec0    │   │  Collection:            │
│  • vec_solution vec0    │   │   context8_store        │
│  • vec_code_context vec0│   │  Named Vectors:         │
│  • fts_records (FTS5)   │   │   • problem  384d       │
│  • records (SQL + JSON1)│   │   • solution 384d       │
│  • WAL mode             │   │   • code_ctx 384/768d   │
│                         │   │  Sparse: keywords       │
└─────────────────────────┘   └─────────────────────────┘
```

---

## Capabilities (and how each backend delivers them)

The same three capabilities work across both backends — only the underlying mechanism differs.

| Capability | SQLite + sqlite-vec (default) | Actian VectorAI DB (optional) |
|---|---|---|
| **Hybrid Fusion** | Dense vec0 KNN + FTS5 BM25, fused with RRF in pure Python | Dense + sparse vectors, fused with `av.reciprocal_rank_fusion` |
| **Filtered Search** | SQL `WHERE` over indexed columns + JSON1 `json_each` for tag arrays | `FilterBuilder` over the payload |
| **Named Vectors** | 3 vec0 virtual tables: `vec_problem`, `vec_solution`, `vec_code_context` | 3 named vector spaces in one collection |

### Prove it: `context8 bench`

The benchmark ablates one feature at a time over a 27-query ground-truth set and prints a side-by-side comparison:

```bash
context8 init --seed
context8 bench
```

The output table shows Recall@1, Recall@3, Recall@5, MRR, and p50 latency for four configurations — `dense only` → `+ named vectors` → `+ hybrid fusion` → `+ filtered search` — with green deltas vs the baseline. Each row turns on one more retrieval feature. The deltas are the proof.

Run it under either backend:

```bash
context8 bench                          # SQLite (default)
CONTEXT8_BACKEND=actian context8 bench  # Actian
```

### See it: `context8 demo`

A live, scripted three-scenario walkthrough designed as the script for a submission video:

```bash
context8 demo
```

1. **Named vectors** — the same record retrieved three ways: by error text, by code pattern, by solution approach. One record, three independent vector spaces.
2. **Hybrid fusion** — `ERESOLVE unable to resolve dependency tree` on dense-only vs. dense + sparse RRF, side by side.
3. **Filtered search** — same query, language filter flipped between `python` and `javascript`, results swap server-side via `FilterBuilder`.

### Verify it: `context8 doctor`

The health check asserts the three features are actually live — no silent degradation:

```
sqlite-vec                ✓  0.1.9
Backend connectivity      ✓  SQLite + sqlite-vec @ ~/.context8/context8.db
Schema                    ✓  records table present (23 rows)
Named vectors (3)         ✓  3 found: code_context, problem, solution
Sparse (FTS5)             ✓  fts_records virtual table present
Hybrid fusion ready       ✓  dense + sparse + RRF available
WAL mode                  ✓  journal_mode=wal
Filtered scroll           ✓  returned N record(s)
```

---

## Tech Stack

| Component | Technology | Purpose |
|---|---|---|
| Vector Storage (default) | [sqlite-vec](https://github.com/asg017/sqlite-vec) | Local KNN over named vector spaces in stock SQLite |
| Lexical Storage (default) | SQLite [FTS5](https://www.sqlite.org/fts5.html) | Native BM25 index, no extra dependency |
| Vector Storage (optional) | [Actian VectorAI DB](https://github.com/hackmamba-io/actian-vectorAI-db-beta) | Hackathon-era backend behind `pip install context8[actian]` |
| Dense Embeddings | `sentence-transformers/all-MiniLM-L6-v2` | 384d text vectors (problems, solutions) |
| Code Embeddings | `microsoft/codebert-base` | 768d code-aware vectors (opt-in via `CONTEXT8_USE_CODE_MODEL=1`) |
| MCP Server | Python `mcp` SDK | stdio transport to agents |
| CLI | Click + Rich | Terminal UX with tables, panels, health checks |
| CI/CD | GitHub Actions | Lint → Test → Build → Publish to PyPI |
| Package | uv / pip / hatchling | PEP 517 compatible |

---

## Seed Data

Context8 ships with **23 curated problem-solution pairs** to solve the cold start problem:

| Category | Count | Examples |
|---|---|---|
| Python environment | 5 | venv conflicts, PEP 668, asyncio in Jupyter, CUDA OOM |
| Node.js / npm | 3 | peer deps, ESM vs CJS, heap out of memory |
| React / Next.js | 3 | hydration mismatch, setState in render, streaming API routes |
| TypeScript | 2 | type narrowing to `never`, path alias resolution |
| Docker | 2 | volume mounts on WSL2, port conflicts |
| Database | 1 | connection pool exhaustion in serverless |
| Git | 1 | lockfile merge conflicts |
| Rust | 2 | WASM `no_std`, borrow checker in loops |
| AI / ML | 2 | OpenAI rate limits, HuggingFace generation issues |
| Build tools | 1 | Vite prebundling cache |
| Cross-platform | 1 | Windows long path ENOENT |

Run `context8 init --seed` to load them. Your agents start finding solutions immediately.

---

## Development

```bash
# Clone and set up
git clone https://github.com/hallelx2/context8.git
cd context8
uv venv && source .venv/bin/activate  # or: .venv\Scripts\activate on Windows

# Install context8 with dev dependencies (SQLite backend works out of the box)
uv pip install -e ".[all]"

# Initialise the local DB and verify
context8 init
context8 doctor

# Run the full test suite (~125 tests, all run against SQLite, no infrastructure)
pytest tests/ -v

# Run the legacy Actian e2e suite — install the extra and start the container first:
uv pip install -e ".[actian]"
docker compose up -d
CONTEXT8_BACKEND=actian pytest tests/ -v

# Lint + format
ruff check src/ tests/
ruff format src/ tests/
```

### Project Structure

```
context8/
├── src/context8/
│   ├── __init__.py
│   ├── __main__.py
│   ├── config.py             # Constants, env-driven backend resolution, paths
│   ├── models.py             # ResolutionRecord, FeedbackStats, Attribution, SearchResult
│   ├── storage/              # Pluggable storage package (NEW)
│   │   ├── backend.py        # StorageBackend Protocol + SearchFilter + ScoredHit
│   │   ├── sqlite_schema.py  # DDL + apply_migrations + dim guard
│   │   ├── sqlite_backend.py # SQLite + sqlite-vec + FTS5 (default backend)
│   │   ├── actian_backend.py # Legacy Actian VectorAI DB backend
│   │   └── service.py        # StorageService env-driven facade
│   ├── agents.py             # Editor MCP config writer (Claude/Cursor/Windsurf)
│   ├── feedback.py           # FeedbackService — agent rate-this-fix loop
│   ├── embeddings/
│   │   ├── service.py        # MiniLM + CodeBERT lazy loaders
│   │   └── tokenizer.py      # BM25 tokenizer (used by ActianBackend.search_sparse)
│   ├── search/
│   │   ├── engine.py         # Backend-agnostic hybrid search + ablation flags
│   │   ├── fusion.py         # Pure-Python Reciprocal Rank Fusion (NEW)
│   │   ├── analyzer.py       # QueryAnalyzer (per-query weight tuning)
│   │   ├── ranking.py        # Confidence + recency + worked-ratio booster
│   │   └── attribution.py    # Per-strategy score tracking (backend-agnostic)
│   ├── ingest/
│   │   ├── pipeline.py       # Generic ingest pipeline
│   │   ├── seed.py           # 23 curated problem-solution starter records
│   │   └── github.py         # GitHub Issues importer (pull resolved bugs)
│   ├── benchmark/
│   │   ├── ground_truth.py   # 27 query→record evaluation pairs
│   │   └── runner.py         # Recall@K / MRR / latency evaluator
│   ├── docker.py             # Container helpers (Actian only — no-ops on SQLite)
│   ├── mcp/
│   │   ├── server.py         # MCP server entry point
│   │   └── tools.py          # 5 MCP tools (search/log/rate/search_solutions/stats)
│   └── cli/
│       ├── main.py           # Click group entry
│       ├── ui.py             # Rich helpers + backend-aware health checks
│       └── commands/
│           ├── lifecycle.py  # start / stop / init (backend-aware)
│           ├── ops.py        # stats / doctor / search / browse / export / import
│           ├── integrations.py  # add / remove (editor configs)
│           ├── bench.py      # bench / demo
│           ├── ingest.py     # import-github / mine
│           └── serve.py      # serve (MCP, backend-aware bootstrap)
├── tests/                    # ~127 unit tests (SQLite default) + Actian e2e (gated)
├── docs/                     # Architecture + build plans (hackathon-era)
├── .github/workflows/        # CI + PyPI release
├── docker-compose.yml        # Actian container — only used under [actian]
├── pyproject.toml
├── RESULTS.md                # Submission deliverable: bench numbers + narrative
└── CLAUDE.md
```

### Releasing

```bash
# Bump version in pyproject.toml and src/context8/__init__.py, then:
git tag v0.2.0
git push --tags
# CI runs → PyPI publishes → GitHub Release created automatically
```

---

## Changelog

### v0.5.0
- **Pluggable storage backends.** SQLite + `sqlite-vec` + FTS5 is now the default — no Docker, no daemon, single-file DB at `~/.context8/context8.db`.
- **Backward-compatible Actian backend.** `pip install context8[actian]` and `CONTEXT8_BACKEND=actian` keep the original hackathon stack working.
- **Search engine refactor.** `search/engine.py` no longer imports a vendor SDK; it talks to a `StorageBackend` Protocol. RRF moved to `search/fusion.py` as pure Python.
- **Backend-aware CLI.** `start`/`stop` print "no daemon needed" under SQLite; `init` runs schema migrations; `doctor` checks file integrity, WAL mode, vec0 + FTS5 modules.
- **Concurrency.** WAL mode + 5s busy timeout for parallel MCP reads while ingest writes.
- **vec0 dim guard.** Flipping `CONTEXT8_USE_CODE_MODEL` after init fails loudly with a `--force` hint instead of silently corrupting the DB.
- **New tests.** `tests/test_storage_sqlite.py` (18 unit tests), `tests/test_e2e_sqlite.py` (full e2e on SQLite), `tests/test_search_filter.py` (filter translation).
- **Fixed pre-existing test bug.** `FeedbackService(storage, embeddings)` arity mismatch in `test_e2e.py:281,300`.

### v0.4.0
- **Container runtime**: Docker + Podman auto-detection with cached probing
- **Self-bootstrapping serve**: `context8 serve` now starts DB, inits collection, and caches models before the MCP loop — works on a cold machine with zero prior setup
- **`--no-bootstrap` flag**: skip auto-bootstrap if you manage infra manually
- **Hybrid search restored**: sparse vector detection now reads collection info on every startup instead of defaulting to False
- **Sparse search fix**: passes `SparseVector` object with `using="keywords"` (was rejected by server)
- **Async MCP fix**: tool calls wrapped in `asyncio.to_thread` — no more event loop blocking
- **Browse resource leak fix**: gRPC client always closed on no-results path
- **Embedding cache fix**: hash full text, not just first 500 chars
- **Configurable dims**: `TEXT_EMBED_DIM` / `CODE_EMBED_DIM` flow through everywhere
- **CodeBERT env var**: `CONTEXT8_USE_CODE_MODEL=1` enables 768d code embeddings
- **Browse + ecosystem MCP tools**: metadata filtering and stack-based discovery for skill writing
- **Auto-capture + auto-suggest hooks**: Claude Code hooks for zero-effort logging and retrieval
- **Session mining**: `context8 mine ~/.claude/sessions/`
- **Export/import**: `context8 export -o backup.json` / `context8 import backup.json`
- **Solution versioning**: same problem, different fix stored as variants
- **Batch ingest**: ~20x faster for GitHub imports and seeding
- **Claude Code plugin install**: `context8 add claude` writes to plugin directory, not settings.json

### v0.3.0
- Auto-start Docker, pre-download models, one-stop `context8 init`
- Docker compose generated in `~/.context8/` for pip-installed users
- Agent config for 6 agents: Claude Code, Claude Desktop, Cursor, VS Code, Windsurf, Gemini

### v0.2.0
- Framework restructure into subpackages
- GitHub Issues importer, feedback loop, quality ranker, per-strategy attribution
- Benchmark suite with Recall@K ablation
- 79 unit tests

### v0.1.0
- Initial release: MCP server, hybrid search, 24 seed records, CLI

## License

[MIT](LICENSE)

---

<p align="center">
  <sub>Originally built for the <a href="https://dorahacks.io/">Actian VectorAI DB Build Challenge</a>. Now SQLite-first; Actian remains a supported optional backend.</sub>
</p>
