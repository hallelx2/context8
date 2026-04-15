# Context8

**Collective problem-solving memory for coding agents — powered by [Actian VectorAI DB](https://github.com/hackmamba-io/actian-vectorAI-db-beta)**

Context7 gives your agent the docs. **Context8 gives it what the docs don't cover.**

Every time a coding agent solves an uncommon error, the solution vanishes after the session. Context8 stores those solutions in a vector database so any agent — yours or your team's — can find them next time.

```
Agent hits error → searches Context8 → finds a past solution → applies it
                                            ↓
                     Agent solves new error → logs it to Context8 → future agents benefit
```

## Prerequisites

- **Docker Desktop** — Actian VectorAI DB runs as a Docker container on your machine
- **Python 3.10+**

## Quick Start

```bash
# 1. Install context8 + the Actian VectorAI DB client (one line)
pip install context8 "actian-vectorai @ https://github.com/hackmamba-io/actian-vectorAI-db-beta/raw/main/actian_vectorai-0.1.0b2-py3-none-any.whl"

# Or with uv
uv pip install context8 "actian-vectorai @ https://github.com/hackmamba-io/actian-vectorAI-db-beta/raw/main/actian_vectorai-0.1.0b2-py3-none-any.whl"

# 2. Start the database (pulls and runs the Docker container)
context8 start

# 3. Initialize and seed with 24 curated problem-solution pairs
context8 init --seed

# 4. Add to your coding agent
context8 add claude       # Claude Code
context8 add cursor       # Cursor
context8 add windsurf     # Windsurf

# 5. Verify everything works
context8 doctor
```

Restart your agent. It now has three new tools: `context8_search`, `context8_log`, and `context8_stats`.

> **Why two packages?** The `actian-vectorai` SDK is distributed by Actian as a beta wheel and is not yet on PyPI. Context8 is on PyPI. Once Actian publishes their SDK to PyPI, this will become a single `pip install context8`.

## What It Does

| Layer | Source | What It Covers |
|-------|--------|----------------|
| **Context 1-6** | Codebase, conversation | Your current project |
| **Context 7** | Official documentation | Common patterns, API usage |
| **Context 8** | Agent problem-solving history | Uncommon errors, workarounds, integration bugs |

Context8 catches the **long tail** — the problems that waste the most agent cycles because they aren't documented anywhere:

- Environment-specific failures (OS quirks, dependency conflicts)
- Library interaction bugs that only surface in combination
- Workarounds discovered through trial-and-error
- Errors that return zero useful Stack Overflow results

## How It Works

Context8 is an [MCP server](https://modelcontextprotocol.io/) backed by Actian VectorAI DB. When your agent encounters an error:

1. **Search** — Agent calls `context8_search("TypeError Cannot read properties of undefined map React Suspense")`
2. **Match** — Context8 runs hybrid search: dense semantic vectors find meaning-similar problems, sparse keyword vectors catch exact error tokens, metadata filters narrow by language/framework
3. **Return** — Agent gets ranked solutions with code diffs, confidence scores, and context
4. **Learn** — After solving a new problem, the agent calls `context8_log(problem=..., solution=...)` to store it

### Three Search Strategies, Fused Together

| Strategy | What It Catches | Example |
|----------|----------------|---------|
| **Dense search** (problem vector, 384d) | Semantic meaning | "undefined array access" matches "null reference on collection" |
| **Dense search** (code context vector, 768d) | Code patterns | `data?.items ?? []` matches `optional chaining null safety` |
| **Sparse search** (BM25 keywords) | Exact tokens | `ModuleNotFoundError` matches `ModuleNotFoundError` exactly |

Results are fused with **Reciprocal Rank Fusion (RRF)** and filtered by language, framework, and more.

## CLI Reference

```bash
context8 start                  # Start the Actian VectorAI DB container
context8 stop                   # Stop the container
context8 init                   # Create the collection
context8 init --seed            # Create + seed with starter data
context8 init --seed --force    # Drop, recreate, and reseed

context8 add claude             # Add to Claude Code (~/.claude/settings.json)
context8 add claude-project     # Add to project-level Claude config
context8 add cursor             # Add to Cursor (.cursor/mcp.json)
context8 add windsurf           # Add to Windsurf (.windsurf/mcp.json)
context8 remove claude          # Remove from Claude Code

context8 stats                  # Show knowledge base statistics
context8 doctor                 # Full health check
context8 search "query"         # Search from the command line (for testing)
context8 search "query" -l python  # Search with language filter

context8 serve                  # Start MCP server (agents call this automatically)
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│              Coding Agent (Claude Code / Cursor)         │
└────────────────────────┬────────────────────────────────┘
                         │ MCP (stdio)
┌────────────────────────▼────────────────────────────────┐
│                  Context8 MCP Server                     │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Embedding   │  │    Search    │  │    Storage   │  │
│  │   Pipeline    │  │    Engine    │  │    Service   │  │
│  │              │  │              │  │              │  │
│  │ MiniLM 384d  │  │ Dense+Sparse │  │ Named Vecs  │  │
│  │ CodeBERT*    │  │ RRF Fusion   │  │ Filters     │  │
│  │ BM25 Sparse  │  │ QueryAnalyze │  │ Dedup       │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└────────────────────────┬────────────────────────────────┘
                         │ gRPC :50051
              ┌──────────▼──────────┐
              │  Actian VectorAI DB │
              │  (Docker)           │
              │                     │
              │  context8_store     │
              │  3 named vectors    │
              │  + sparse + payload │
              └─────────────────────┘
```

## Hackathon: Advanced Features Used

This project uses **all three** advanced features required by the Actian VectorAI DB Build Challenge:

1. **Hybrid Fusion** — Dense semantic vectors + sparse BM25 keyword vectors, fused with RRF. Error messages need both semantic understanding *and* exact token matching.

2. **Filtered Search** — Metadata filters narrow results by language, framework, error type, and resolution status. A Python agent doesn't need TypeScript solutions.

3. **Named Vectors** — Three separate embedding spaces (`problem` 384d, `solution` 384d, `code_context` 768d) because error descriptions, fix descriptions, and code snippets are semantically different domains.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Vector Database | Actian VectorAI DB (Docker, gRPC) |
| Dense Embeddings | sentence-transformers/all-MiniLM-L6-v2 (384d) |
| Code Embeddings | microsoft/codebert-base (768d, opt-in) |
| Sparse Embeddings | Custom BM25 tokenizer |
| MCP Server | Python `mcp` SDK (stdio transport) |
| CLI | Click + Rich |
| Package Manager | uv / pip compatible |

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

# Run tests
pytest tests/ -v

# Lint
ruff check src/
```

## Project Structure

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
├── tests/
├── docs/                   # Architecture, plans, bottleneck analysis
├── docker-compose.yml
├── pyproject.toml
└── CLAUDE.md               # Agent instructions for this codebase
```

## License

MIT
