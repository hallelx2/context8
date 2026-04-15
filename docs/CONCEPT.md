# Context8 — Collective Problem-Solving Memory for Coding Agents

## The Problem

When coding agents (Claude Code, Cursor, Copilot, Aider, etc.) encounter errors, they solve them in isolation. Every solution disappears into the void after the session ends. There is no persistent, searchable memory of what went wrong and how it was fixed.

**Context7** (from Upstash) solves documentation lookup — searching official docs, READMEs, common usage patterns. That covers the *known knowns* — the well-documented, frequently-asked questions.

But there is an entire category of problems that Context7 cannot help with:

- **Uncommon errors** that don't appear in official docs
- **Environment-specific failures** (OS quirks, dependency conflicts, version mismatches)
- **Integration bugs** where two libraries interact in undocumented ways
- **Workarounds** that only emerge from trial-and-error in real codebases
- **Agent-discovered fixes** that no human has written a Stack Overflow answer for

These are the *unknown unknowns*. The long tail of coding problems. And they are **exactly** the problems that waste the most agent cycles — the agent spins, retries, hallucinates, and eventually gives up or produces a fragile fix.

## The Solution: Context8

**Context8** is an MCP server backed by Actian VectorAI DB that acts as a collective problem-solving memory for coding agents.

### How It Works

```
Agent encounters an error
        │
        ▼
┌─────────────────────┐
│  Search Context8    │ ◄── "Has any agent solved something like this before?"
│  (Hybrid Search)    │
└─────────┬───────────┘
          │
    ┌─────┴──────┐
    │            │
  Found      Not Found
    │            │
    ▼            ▼
  Return     Agent solves
  solution   it normally
    │            │
    │            ▼
    │     ┌─────────────────┐
    │     │ Log to Context8 │ ◄── Problem + Solution + Context stored
    │     └─────────────────┘
    │            │
    ▼            ▼
  Agent uses   Future agents
  past fix     can find this
```

### The Three Layers of Coding Agent Context

| Layer | Source | Covers | Provider |
|-------|--------|--------|----------|
| **Context1-6** | Codebase, conversation, memory | Current project state | Built into agent |
| **Context7** | Official documentation | Common patterns, API usage, known solutions | Upstash |
| **Context8** | Agent problem-solving history | Uncommon errors, workarounds, integration bugs, agent-discovered fixes | **Actian VectorAI DB** |

### Why This Needs a Vector Database

The problems Context8 stores are not keyword-searchable in any useful way. Consider:

- **Problem:** `"TypeError: Cannot read properties of undefined (reading 'map') when using React Query v5 with Suspense boundary and custom error boundary wrapping a lazy-loaded component"`
- **Similar problem an agent solved last week:** `"Undefined array access in React Query suspense mode after upgrading from v4 — data is undefined on first render before query resolves"`

A keyword search would miss this. The terms are completely different. But a **semantic search** with the right embedding model would score these as highly similar — because the *meaning* is the same: React Query + Suspense + undefined data on initial render.

Now add **hybrid search** — combine semantic similarity with exact keyword matching:
- Dense vectors catch the *meaning* (React Query + Suspense + race condition)
- Sparse vectors catch the *exact tokens* (`TypeError`, `Cannot read properties of undefined`, `'map'`)

This is where Actian VectorAI DB's hybrid fusion (RRF + DBSF), named vectors, and filtered search become critical.

## What Gets Stored

Every time a coding agent resolves a non-trivial problem, Context8 logs a **resolution record**:

```json
{
  "problem": {
    "description": "TypeError: Cannot read properties of undefined (reading 'map')",
    "error_type": "TypeError",
    "stack_trace": "at UserList (src/components/UserList.tsx:15:28)...",
    "context": "Using React Query v5 useQuery with Suspense enabled, data is undefined on first render"
  },
  "solution": {
    "description": "Added fallback check: const users = data?.users ?? []. The issue is that with Suspense mode, React Query can return undefined briefly between the suspend boundary catch and data resolution",
    "code_diff": "- const users = data.users.map(...)\n+ const users = (data?.users ?? []).map(...)",
    "confidence": 0.92
  },
  "metadata": {
    "language": "typescript",
    "framework": "react",
    "libraries": ["@tanstack/react-query@5.x", "react@18.x"],
    "agent": "claude-code",
    "timestamp": "2026-04-14T10:30:00Z",
    "resolution_time_seconds": 34,
    "file_patterns": ["*.tsx"],
    "os": "windows",
    "node_version": "20.x",
    "tags": ["suspense", "race-condition", "undefined-access"]
  }
}
```

## What Makes This Different from a Log File

| Feature | Log File | Stack Overflow | Context8 |
|---------|----------|----------------|----------|
| Semantic search | No | Partial (title matching) | Yes — dense + sparse hybrid |
| Agent-native (MCP) | No | No | Yes — native MCP tool |
| Structured metadata | No | Tags only | Full structured payload with filters |
| Auto-populated | No | Human-written | Agent writes automatically |
| Cross-project | No | Yes | Yes — local + cloud sync |
| Code context | No | Copy-paste snippets | Full diff + surrounding code |
| Confidence scoring | No | Upvotes (noisy) | Agent self-assessed + retrieval score |
| Multi-modal | No | No | Named vectors (problem/solution/code) |

## Technical Requirements (Hackathon)

The hackathon requires going beyond basic similarity search. Context8 uses **all three** advanced features:

1. **Hybrid Fusion** — Dense semantic vectors + sparse BM25-style keyword vectors, fused with RRF/DBSF. Essential because error messages contain both semantic meaning AND exact tokens (class names, error codes).

2. **Filtered Search** — Metadata filters narrow results by language, framework, OS, recency, library versions. An agent working in Python doesn't need TypeScript solutions.

3. **Named Vectors** — Three separate embedding spaces:
   - `problem` vector (384d) — the error description and symptoms
   - `solution` vector (384d) — the fix description and approach
   - `code_context` vector (768d) — the surrounding code where the error occurred

## Target Users

1. **Individual developers** — Run Context8 locally. Your own agent builds up a personal knowledge base over time.
2. **Teams** — Cloud-synced Context8. Every team member's agent contributes to and benefits from a shared problem-solving memory.
3. **Open source communities** — Public Context8 instances for specific ecosystems (React, Python ML, Rust, etc.).

## Name Origin

Context8 follows Context7 in the same way that "the next layer" of context for coding agents. Context7 gives you the docs. Context8 gives you what the docs don't cover.
