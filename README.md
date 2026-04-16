<p align="center">
  <img src="https://img.shields.io/badge/Context8-Agent%20Memory-blueviolet?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCI+PHBhdGggZD0iTTEyIDJhMTAgMTAgMCAxIDAgMCAyMCAxMCAxMCAwIDAgMCAwLTIweiIvPjxwYXRoIGQ9Ik0xMiA2djEyIi8+PHBhdGggZD0iTTYgMTJoMTIiLz48L3N2Zz4=" alt="Context8">
</p>

<h1 align="center">Context8</h1>

<p align="center">
  <strong>Collective problem-solving memory for coding agents</strong><br>
  <em>Powered by <a href="https://github.com/hackmamba-io/actian-vectorAI-db-beta">Actian VectorAI DB</a></em>
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
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | Runs the Actian VectorAI DB container locally |
| Python 3.10+ | Runs the Context8 CLI and MCP server |

## Quick Start

```bash
# 1. Install context8 + the Actian VectorAI DB client
pip install context8 "actian-vectorai @ https://github.com/hackmamba-io/actian-vectorAI-db-beta/raw/main/actian_vectorai-0.1.0b2-py3-none-any.whl"

# Or with uv
uv pip install context8 "actian-vectorai @ https://github.com/hackmamba-io/actian-vectorAI-db-beta/raw/main/actian_vectorai-0.1.0b2-py3-none-any.whl"

# 2. Start the database (pulls and runs the Docker container)
context8 start

# 3. Initialize and seed with 24 curated problem-solution pairs
context8 init --seed

# 4. Add to your coding agent (pick one)
context8 add claude       # Claude Code
context8 add cursor       # Cursor
context8 add windsurf     # Windsurf

# 5. Verify everything works
context8 doctor
```

Restart your agent. It now has three new tools: **`context8_search`**, **`context8_log`**, and **`context8_stats`**.

> **Why two packages?** The `actian-vectorai` SDK is distributed by Actian as a beta wheel and is not yet on PyPI. Context8 is on PyPI. Once Actian publishes their SDK to PyPI, this becomes a single `pip install context8`.

---

## Context8 vs Context7 vs Skills

Coding agents have multiple ways to get help. Here's where each one fits and where it falls short:

### The Context Layers

| Layer | Source | What It Covers | Limits |
|---|---|---|---|
| **Context 1–6** | Codebase, conversation, memory | Your current project's files and history | Only knows *your* code |
| **Context7** | Official documentation (Upstash) | API references, common usage patterns, getting-started guides | Only covers *documented* knowledge |
| **Skills / CLAUDE.md** | Hand-written rules | Project conventions, tool-specific patterns, coding style | Manual maintenance, doesn't learn |
| **Context8** | Agent problem-solving history (Actian VectorAI DB) | Uncommon errors, workarounds, integration bugs, agent-discovered fixes | Needs seeding and accumulation |

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

Context8 is an [MCP server](https://modelcontextprotocol.io/) backed by Actian VectorAI DB. When your agent encounters an error:

1. **Search** — Agent calls `context8_search("TypeError Cannot read properties of undefined map React Suspense")`
2. **Match** — Context8 runs hybrid search: dense semantic vectors find meaning-similar problems, sparse keyword vectors catch exact error tokens, metadata filters narrow by language/framework
3. **Return** — Agent gets ranked solutions with code diffs, confidence scores, and context
4. **Learn** — After solving a new problem, the agent calls `context8_log(problem=..., solution=...)` to store it

### Three Search Strategies, Fused Together

| Strategy | Vector Space | What It Catches | Example |
|---|---|---|---|
| **Dense search** | `problem` (384d, MiniLM) | Semantic meaning | "undefined array access" matches "null reference on collection" |
| **Dense search** | `code_context` (768d, CodeBERT) | Code patterns | `data?.items ?? []` matches `optional chaining null safety` |
| **Sparse search** | `keywords` (BM25) | Exact tokens | `ModuleNotFoundError` matches `ModuleNotFoundError` exactly |

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
context8 start                  # Start the Actian VectorAI DB container
context8 stop                   # Stop the container
context8 init                   # Create the collection
context8 init --seed            # Create + seed with starter data
context8 init --seed --force    # Drop, recreate, and reseed
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
context8 stats                  # Show knowledge base statistics
context8 doctor                 # Full health check (Docker, DB, SDK, models, agents)
context8 search "query"         # Search from the command line
context8 search "query" -l python  # Search with language filter
context8 serve                  # Start MCP server (agents call this automatically)
```

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
│  │   Embedding    │  │    Search     │  │    Storage     │  │
│  │   Pipeline     │  │    Engine     │  │    Service     │  │
│  │                │  │               │  │                │  │
│  │  MiniLM 384d   │  │  Dense+Sparse │  │  Named Vecs   │  │
│  │  CodeBERT 768d │  │  RRF Fusion   │  │  Filters      │  │
│  │  BM25 Sparse   │  │  QueryAnalyze │  │  Dedup        │  │
│  └────────────────┘  └───────────────┘  └────────────────┘  │
└──────────────────────────┬──────────────────────────────────┘
                           │ gRPC :50051
                ┌──────────▼──────────┐
                │  Actian VectorAI DB │
                │  (Docker Container) │
                │                     │
                │  Collection:        │
                │   context8_store    │
                │                     │
                │  Named Vectors:     │
                │   • problem  384d   │
                │   • solution 384d   │
                │   • code_ctx 768d   │
                │  Sparse: keywords   │
                │  Payload: metadata  │
                └─────────────────────┘
```

---

## Hackathon: Advanced Features Used

> Built for the [Actian VectorAI DB Build Challenge](https://dorahacks.io/)

This project uses **all three** advanced features required by the hackathon:

| Feature | How Context8 Uses It | Why It Matters |
|---|---|---|
| **Hybrid Fusion** | Dense semantic + sparse BM25 keyword vectors, fused with RRF | Error messages contain both *meaning* and *exact tokens* — you need both |
| **Filtered Search** | Metadata filters by language, framework, error type, resolution status | A Python agent doesn't need TypeScript solutions |
| **Named Vectors** | 3 separate spaces: `problem` (384d), `solution` (384d), `code_context` (768d) | Error descriptions, fix descriptions, and code are semantically different domains |

---

## Tech Stack

| Component | Technology | Purpose |
|---|---|---|
| Vector Database | [Actian VectorAI DB](https://github.com/hackmamba-io/actian-vectorAI-db-beta) | Storage, indexing, HNSW search |
| Dense Embeddings | `sentence-transformers/all-MiniLM-L6-v2` | 384d text vectors (problems, solutions) |
| Code Embeddings | `microsoft/codebert-base` | 768d code-aware vectors (opt-in) |
| Sparse Embeddings | Custom BM25 tokenizer | Exact keyword matching |
| MCP Server | Python `mcp` SDK | stdio transport to agents |
| CLI | Click + Rich | Terminal UX with tables, panels, health checks |
| CI/CD | GitHub Actions | Lint → Test → Build → Publish to PyPI |
| Package | uv / pip / hatchling | PEP 517 compatible |

---

## Seed Data

Context8 ships with **24 curated problem-solution pairs** to solve the cold start problem:

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

# Install context8 + dev deps + actian client
uv pip install -e ".[all]" "actian-vectorai @ https://github.com/hackmamba-io/actian-vectorAI-db-beta/raw/main/actian_vectorai-0.1.0b2-py3-none-any.whl"

# Start the DB and verify
context8 start
context8 doctor

# Run tests (29 unit tests, no DB needed)
pytest tests/ -v

# Lint + format
ruff check src/ tests/
ruff format src/ tests/
```

### Project Structure

```
context8/
├── src/context8/
│   ├── cli.py              # CLI commands (start/stop/init/add/remove/stats/doctor/search)
│   ├── server.py           # MCP server (context8_search, context8_log, context8_stats)
│   ├── agents.py           # Agent config management (add/remove from Claude/Cursor/etc.)
│   ├── search.py           # Hybrid search engine + QueryAnalyzer
│   ├── embeddings.py       # MiniLM + CodeBERT + BM25 pipeline
│   ├── storage.py          # Actian VectorAI DB operations (with sparse fallback)
│   ├── models.py           # ResolutionRecord dataclass
│   ├── config.py           # Constants, paths, agent registry
│   └── seed.py             # 24 curated problem-solution starter records
├── tests/                  # 29 unit tests (models, tokenizer, agents, query analyzer)
├── docs/                   # Architecture, 8 build plans, bottleneck analysis
├── .github/workflows/
│   ├── ci.yml              # Lint → Test (3.10 + 3.12) → Build
│   └── publish.yml         # CI → Publish to PyPI → GitHub Release
├── docker-compose.yml
├── pyproject.toml
└── CLAUDE.md               # Agent instructions for this codebase
```

### Releasing

```bash
# Bump version in pyproject.toml and src/context8/__init__.py, then:
git tag v0.2.0
git push --tags
# CI runs → PyPI publishes → GitHub Release created automatically
```

---

## License

[MIT](LICENSE)

---

<p align="center">
  <sub>Built with Actian VectorAI DB for the <a href="https://dorahacks.io/">Actian VectorAI DB Build Challenge</a></sub>
</p>
