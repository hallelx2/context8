# Bottlenecks, Risks & Mitigations

## Overview

This document catalogs every known bottleneck, risk, and limitation in Context8, along with concrete mitigations. These are the things that will bite you at demo time if you don't plan for them.

---

## 1. Cold Start Problem

**Severity: HIGH**
**Impact: Users abandon Context8 before it becomes useful**

### The Problem
A new Context8 instance has zero records. When agents search and find nothing, they stop using the tool. The database never accumulates data. This is a death spiral.

### Mitigations

| Strategy | Effort | Effectiveness |
|----------|--------|--------------|
| Curated seed dataset (60+ records) | 1 hour | HIGH — immediate value on first search |
| Auto-learning mode (lower dedup threshold early) | 15 min | MEDIUM — faster accumulation |
| Community seed packs (v2) | 4 hours | HIGH — ecosystem-specific starter data |
| Import from existing sources (Stack Overflow, GitHub Issues) | 2 hours | MEDIUM — requires data cleaning |

**Recommendation for hackathon:** Ship the curated seed dataset (Plan 07). It's the highest ROI.

---

## 2. Embedding Model Load Time

**Severity: MEDIUM**
**Impact: First MCP call takes 5-10 seconds instead of <200ms**

### The Problem
Loading `all-MiniLM-L6-v2` (80MB) and `microsoft/codebert-base` (440MB) from disk takes 2-4 seconds each. The first time an agent calls `context8_search` or `context8_log`, they wait 5+ seconds for both models to load.

### Mitigations

| Strategy | Effort | Effectiveness |
|----------|--------|--------------|
| Lazy loading (default) | Already built | PARTIAL — defers but doesn't eliminate |
| Background preload on server start | 10 min | HIGH — hides load time behind startup |
| Model warm-up ping on init | 5 min | HIGH — embed a dummy text on startup |
| Quantized models (ONNX) | 2 hours | HIGH — 2-3x faster loading |
| Single model for all spaces | 5 min | MEDIUM — lose code-specific accuracy |

**Recommendation for hackathon:** Background preload + model warm-up ping.

```python
# In server.py, during initialization:
import threading

def _warmup():
    """Preload models in background."""
    embedding_service.embed_text("warmup")
    embedding_service.embed_code("def warmup(): pass")

threading.Thread(target=_warmup, daemon=True).start()
```

---

## 3. Memory Usage

**Severity: MEDIUM**
**Impact: May be too heavy for resource-constrained dev machines**

### The Problem
Component memory usage:

| Component | RAM Usage |
|-----------|-----------|
| Actian VectorAI DB (Docker) | ~200-500MB |
| MiniLM-L6-v2 model | ~160MB |
| CodeBERT-base model | ~880MB |
| MCP server process | ~50MB |
| **Total** | **~1.3-1.5 GB** |

On a machine already running an IDE, browser, and Docker, this adds up.

### Mitigations

| Strategy | Effort | Effectiveness |
|----------|--------|--------------|
| Lazy load CodeBERT only when needed | Already built | HIGH — saves 880MB if not used |
| Use MiniLM for ALL vector spaces | 5 min | HIGH — 880MB savings, accuracy tradeoff |
| Use quantized models (float16) | 1 hour | MEDIUM — ~40% memory reduction |
| Docker memory limits | 5 min | Safety net |
| Use distilled model (Model2Vec) | 2 hours | HIGH — orders of magnitude smaller |

**Recommendation for hackathon:** Default to MiniLM for all vectors. Add CodeBERT as opt-in `--high-accuracy` flag.

---

## 4. Sparse Vector Support

**Severity: MEDIUM**
**Impact: Hybrid search may degrade to dense-only**

### The Problem
From the Actian VectorAI DB README:
> **Sparse-Vector Collections:** Sparse-only collections are under server development

Sparse vector support may be incomplete in the beta. If `SparseVectorParams` fails at collection creation time, the hybrid search pipeline breaks.

### Mitigations

| Strategy | Effort | Effectiveness |
|----------|--------|--------------|
| Graceful fallback to dense-only search | 30 min | HIGH — system still works |
| Simulate sparse via dense (embed keywords separately) | 45 min | MEDIUM — approximation |
| Use payload text search instead of sparse vectors | 30 min | MEDIUM — slower but works |
| Test sparse support immediately (Plan 01) | 5 min | CRITICAL — know early |

**Recommendation for hackathon:** Test sparse vectors in Plan 01. If unsupported, fall back to keyword filtering via payload `text` field type instead.

```python
# Fallback: filter-based keyword matching instead of sparse search
from actian_vectorai import Field, FilterBuilder

# Instead of sparse search, use text field filter
f = FilterBuilder().must(Field("problem_text").text("TypeError")).build()
results = client.points.search(
    collection, vector=dense_query, filter=f, limit=10
)
```

---

## 5. Server-Side Unimplemented Features

**Severity: LOW-MEDIUM**
**Impact: Some SDK features error at runtime**

### The Problem
From the README: 44 of 67 SDK methods are fully available. Notable gaps:

- `create_field_index()` — UNIMPLEMENTED (affects filtered search performance)
- `set_payload()` / `overwrite_payload()` / `delete_payload()` — may not work
- Sparse-only collections — under development

### Mitigations

| Gap | Workaround |
|-----|-----------|
| `create_field_index()` | Rely on default indexing; for hackathon scale (<10K records) this is fine |
| Payload mutation | Delete + re-insert the entire point instead of mutating payload |
| Sparse-only collections | Use hybrid collection (dense + sparse) — already our design |

**Recommendation:** Don't depend on any UNIMPLEMENTED features. Design around them.

---

## 6. Search Quality / Relevance

**Severity: HIGH**
**Impact: Agents get wrong/irrelevant results, lose trust**

### The Problem
Embedding quality varies dramatically by domain. A general-purpose model may not understand that `data?.items ?? []` and `optional chaining null safety` are the same concept in code context.

### Mitigations

| Strategy | Effort | Effectiveness |
|----------|--------|--------------|
| Ground truth evaluation (30 QA pairs) | 1 hour | HIGH — measure before you ship |
| Tune fusion weights per query type | 30 min | HIGH — QueryAnalyzer |
| Score threshold filtering (reject <0.1) | 5 min | MEDIUM — no-result better than bad result |
| Confidence field on records | Already built | MEDIUM — weight by solution quality |
| Allow agents to provide feedback | 2 hours | HIGH (v2) — reinforcement learning |

**Recommendation for hackathon:** Build the ground truth evaluation (Plan 07/08) and tune weights until Recall@3 >= 0.8.

---

## 7. Data Quality / Garbage In

**Severity: MEDIUM**
**Impact: DB fills with low-quality or wrong solutions**

### The Problem
Agents don't always produce correct solutions. If an agent logs a wrong fix, future agents find and apply it — spreading the bad solution.

### Mitigations

| Strategy | Effort | Effectiveness |
|----------|--------|--------------|
| Confidence score requirement (>0.6 to log) | 5 min | MEDIUM |
| Deduplication with merge (increment count) | Already built | HIGH — popular solutions rise |
| Agent feedback tool (mark as wrong) | 1 hour | HIGH (v2) |
| Decay old/unused records | 30 min | MEDIUM — stale solutions fade |
| Human review dashboard | 4 hours | HIGH (v2) |

**Recommendation for hackathon:** Enforce minimum confidence threshold + dedup with occurrence counting.

---

## 8. Concurrency / Race Conditions

**Severity: LOW**
**Impact: Duplicate records if multiple agents log simultaneously**

### The Problem
If two agents solve the same problem at the same time and both call `context8_log`, the dedup check may not catch the second one (first hasn't been indexed yet).

### Mitigations

| Strategy | Effort | Effectiveness |
|----------|--------|--------------|
| Optimistic locking (search before insert) | Already built | PARTIAL |
| Post-insert dedup job (background cleanup) | 1 hour | HIGH |
| Accept low-rate duplicates (merge later) | 0 min | PRAGMATIC |

**Recommendation for hackathon:** Accept it. Low probability, easy to merge later.

---

## 9. Docker / Infrastructure Fragility

**Severity: LOW**
**Impact: DB becomes unavailable, MCP tools fail**

### The Problem
If Docker crashes, the DB container stops, or the port is already in use, Context8 becomes completely unavailable.

### Mitigations

| Strategy | Effort | Effectiveness |
|----------|--------|--------------|
| `restart: unless-stopped` in docker-compose | Already configured | HIGH |
| Health check in MCP server startup | 10 min | HIGH |
| Graceful degradation (return "unavailable" not crash) | 15 min | HIGH |
| Connection retry with exponential backoff | 30 min | MEDIUM |

**Recommendation for hackathon:** Health check + graceful error message.

```python
# In server.py
try:
    storage_service.initialize()
except Exception as e:
    logger.error(f"Cannot connect to Actian VectorAI DB: {e}")
    logger.error("Is Docker running? Try: docker compose up -d")
    # Server still starts — returns "unavailable" for all tool calls
```

---

## 10. Cross-Platform Compatibility

**Severity: MEDIUM**
**Impact: Windows users hit path/encoding/Docker issues**

### The Problem
Docker on Windows (WSL2) has quirks:
- Volume mount paths must use Linux format
- File permissions may differ
- Docker Desktop needs to be running

### Mitigations

| Strategy | Effort | Effectiveness |
|----------|--------|--------------|
| Test on Windows specifically | 30 min | HIGH |
| Provide PowerShell startup script | Already planned | HIGH |
| Document WSL2 requirements | 15 min | HIGH |
| Use `pathlib` for all paths in Python | Built-in | MEDIUM |

---

## Risk Matrix Summary

| Risk | Probability | Impact | Priority | Status |
|------|------------|--------|----------|--------|
| Cold start (empty DB) | HIGH | HIGH | P0 | Mitigated (seed data) |
| Model load time | HIGH | MEDIUM | P1 | Mitigated (preload) |
| Sparse vector unsupported | MEDIUM | MEDIUM | P1 | Fallback ready |
| Search quality issues | MEDIUM | HIGH | P1 | Ground truth eval |
| Memory usage too high | LOW | MEDIUM | P2 | Lazy loading |
| Data quality (wrong solutions) | MEDIUM | MEDIUM | P2 | Confidence threshold |
| Server-side gaps | LOW | LOW | P3 | Designed around |
| Concurrency races | LOW | LOW | P3 | Accept for MVP |
| Docker failures | LOW | MEDIUM | P2 | Graceful degradation |
| Windows compat | MEDIUM | MEDIUM | P2 | Test + document |
