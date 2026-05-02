> _Historical hackathon artifact._ Context8 is now SQLite-first by default; the Actian backend is optional. See [README.md](../README.md) and [CLAUDE.md](../CLAUDE.md) for the current architecture.

# Context8 — System Architecture

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Coding Agent (Host)                         │
│  Claude Code / Cursor / Copilot / Aider / any MCP-compatible agent │
└────────────────────────────┬────────────────────────────────────────┘
                             │ MCP Protocol (stdio / SSE)
                             │
┌────────────────────────────▼────────────────────────────────────────┐
│                     Context8 MCP Server                            │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │  search_     │  │  log_        │  │  list_recent_            │  │
│  │  solutions   │  │  solution    │  │  solutions               │  │
│  └──────┬───────┘  └──────┬───────┘  └────────────┬─────────────┘  │
│         │                 │                        │                │
│  ┌──────▼─────────────────▼────────────────────────▼─────────────┐  │
│  │                   Core Engine                                 │  │
│  │                                                               │  │
│  │  ┌─────────────────┐  ┌────────────────┐  ┌───────────────┐  │  │
│  │  │ Embedding Layer │  │ Dedup Engine   │  │ Query Builder │  │  │
│  │  │                 │  │                │  │               │  │  │
│  │  │ • MiniLM (384d) │  │ • Similarity   │  │ • Dense       │  │  │
│  │  │ • CodeBERT(768d)│  │   threshold    │  │ • Sparse      │  │  │
│  │  │ • BM25 sparse   │  │ • Exact match  │  │ • Hybrid RRF  │  │  │
│  │  └────────┬────────┘  └───────┬────────┘  │ • Filters     │  │  │
│  │           │                   │           └───────┬───────┘  │  │
│  └───────────┼───────────────────┼───────────────────┼──────────┘  │
│              │                   │                   │              │
│  ┌───────────▼───────────────────▼───────────────────▼──────────┐  │
│  │              Actian VectorAI DB Client                        │  │
│  │              (actian_vectorai Python SDK)                     │  │
│  └──────────────────────────┬───────────────────────────────────┘  │
└─────────────────────────────┼───────────────────────────────────────┘
                              │ gRPC :50051
                              │
              ┌───────────────▼───────────────┐
              │     Actian VectorAI DB        │
              │     (Docker Container)        │
              │                               │
              │  Collection: context8_store   │
              │  ┌─────────────────────────┐  │
              │  │ Named Vectors:          │  │
              │  │  • problem (384d, cos)  │  │
              │  │  • solution (384d, cos) │  │
              │  │  • code_ctx (768d, cos) │  │
              │  │ Sparse Vectors:         │  │
              │  │  • keywords (BM25)      │  │
              │  │ Payload:                │  │
              │  │  • Full metadata        │  │
              │  │  • Indexed fields       │  │
              │  └─────────────────────────┘  │
              │                               │
              │  Volume: ./data:/data         │
              └───────────────────────────────┘
```

## Component Breakdown

### 1. MCP Server Layer

The MCP (Model Context Protocol) server is the interface between coding agents and Context8. It exposes tools that agents can call.

**Transport:** stdio (local) or SSE (remote/cloud)

**Tools Exposed:**

| Tool | Input | Output | Description |
|------|-------|--------|-------------|
| `context8_search` | query text, optional filters | Ranked list of past solutions | Hybrid search over problem-solving history |
| `context8_log` | problem + solution + metadata | Confirmation + ID | Log a resolved problem for future retrieval |
| `context8_get` | record ID | Full resolution record | Get complete details of a specific record |
| `context8_list_recent` | optional filters, limit | Recent records | Browse recent entries with filtering |
| `context8_stats` | none | Collection statistics | Health check + counts by category |

### 2. Embedding Layer

Three parallel embedding pipelines process different aspects of each record:

```
Input Record
    │
    ├──► Problem text ──► MiniLM-L6-v2 ──► 384d dense vector ("problem")
    │
    ├──► Solution text ──► MiniLM-L6-v2 ──► 384d dense vector ("solution")
    │
    ├──► Code snippet ──► CodeBERT-base ──► 768d dense vector ("code_context")
    │
    └──► All text ──► BM25 tokenizer ──► Sparse vector ("keywords")
```

**Why three separate models:**
- Problem descriptions and solution descriptions exist in different semantic spaces. "TypeError when accessing array" (problem) is semantically different from "Added null check before iteration" (solution), but both relate to the same resolution.
- Code context requires a code-aware model. Natural language models don't understand that `data?.users ?? []` is a null-safe access pattern.
- BM25 sparse vectors capture exact tokens that dense models normalize away — specific class names, error codes, library versions.

### 3. Deduplication Engine

Before storing a new record, Context8 checks for duplicates:

```python
# Step 1: Search for similar existing records
existing = search(problem_vector, threshold=0.95)

# Step 2: If high similarity found
if existing and existing[0].score > 0.95:
    # Update existing record instead of creating new one
    merge_records(existing[0], new_record)
else:
    # Store as new record
    store(new_record)
```

**Merge strategy:**
- Increment `occurrence_count` on the existing record
- Update `last_seen` timestamp
- Append new solution variant if different approach
- Update confidence score based on repeated success

### 4. Query Builder

Constructs the optimal search strategy based on the input:

```python
# Simple text query → dense-only search
"TypeError in React component" → search(problem_vector, limit=10)

# Query with code → hybrid (dense + code context)
"error in: const x = data.map()" → search(problem + code_context vectors)

# Query with filters → filtered hybrid
"Python TypeError in Django" → search(dense, filter=language:python AND framework:django)

# Query with exact error → weighted hybrid (lean toward sparse)
"ModuleNotFoundError: No module named 'cv2'" → search(dense + sparse, weights=[0.3, 0.7])
```

### 5. Actian VectorAI DB Storage

**Collection Schema:**

```python
# Named dense vectors
vectors_config = {
    "problem":      VectorParams(size=384, distance=Distance.Cosine),
    "solution":     VectorParams(size=384, distance=Distance.Cosine),
    "code_context": VectorParams(size=768, distance=Distance.Cosine),
}

# Sparse vectors for keyword matching
sparse_vectors_config = {
    "keywords": SparseVectorParams(),
}

# Payload (metadata stored alongside vectors)
payload = {
    # Searchable / filterable
    "language":     str,     # "python", "typescript", "rust"
    "framework":    str,     # "react", "django", "fastapi"
    "error_type":   str,     # "TypeError", "ImportError"
    "agent":        str,     # "claude-code", "cursor", "copilot"
    "os":           str,     # "windows", "linux", "macos"
    "resolved":     bool,    # True if confirmed working
    "timestamp":    str,     # ISO 8601 datetime
    "tags":         list,    # ["suspense", "race-condition"]
    "libraries":    list,    # ["react@18.x", "react-query@5.x"]

    # Display / context (not filtered, just returned)
    "problem_text":         str,
    "solution_text":        str,
    "code_snippet":         str,
    "code_diff":            str,
    "stack_trace":          str,
    "file_path":            str,
    "confidence":           float,
    "occurrence_count":     int,
    "resolution_time_secs": int,
}
```

## Data Flow: Logging a Solution

```
1. Agent resolves a problem
2. Agent calls context8_log(problem, solution, metadata)
3. MCP Server receives the call
4. Embedding Layer generates:
   - problem_vector (MiniLM, 384d)
   - solution_vector (MiniLM, 384d)
   - code_context_vector (CodeBERT, 768d)
   - keywords_sparse (BM25)
5. Dedup Engine checks for existing similar records (threshold=0.95)
6. If new: upsert point to Actian VectorAI DB
7. If duplicate: merge with existing record
8. Return confirmation + record ID to agent
```

## Data Flow: Searching for a Solution

```
1. Agent encounters an error
2. Agent calls context8_search(query, filters)
3. MCP Server receives the call
4. Embedding Layer generates query vectors (problem + code_context + sparse)
5. Query Builder constructs search strategy:
   a. Dense search on "problem" named vector (limit=50)
   b. Dense search on "code_context" named vector (limit=50)
   c. Sparse search on "keywords" (limit=50)
   d. Apply metadata filters (language, framework, etc.)
6. Hybrid Fusion merges results (RRF with configurable weights)
7. Return top-K results with payloads to agent
8. Agent uses past solution to inform its current approach
```

## Deployment Modes

### Local Mode (Default)

```
Developer Machine
├── Coding Agent (Claude Code)
├── Context8 MCP Server (Python process)
└── Actian VectorAI DB (Docker container, port 50051)
    └── Volume: ./data (persistent storage)
```

- Zero network dependency
- Data stays on machine
- Sub-millisecond latency
- Single `docker compose up` to start

### Cloud Mode (Stretch Goal)

```
Developer Machine                          Cloud Server
├── Coding Agent                          ├── Context8 Cloud API
├── Context8 MCP Server ◄──── sync ────► ├── Actian VectorAI DB
└── Actian VectorAI DB (local)           └── Shared across team
```

- Local instance for speed
- Background sync to cloud for team sharing
- Snapshot-based sync (`save_snapshot` / `load_snapshot`)
- Conflict resolution: last-write-wins with occurrence_count merge

## Technology Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| Vector Database | Actian VectorAI DB (Docker) | Hackathon requirement, named vectors + hybrid + filtered search |
| MCP Server | Python + `mcp` SDK | Native Python, matches DB client |
| Dense Embeddings (text) | sentence-transformers/all-MiniLM-L6-v2 | Fast (384d), good quality, runs locally |
| Dense Embeddings (code) | microsoft/codebert-base | Code-aware, understands syntax patterns |
| Sparse Embeddings | Custom BM25 tokenizer | Exact token matching for error codes |
| Package Format | Python library (pip installable) | Easy distribution, `context8` command |
| Container Runtime | Docker / Docker Compose | Cross-platform, single command startup |
