# Plan 02 — Embedding Pipeline

## Objective

Build the embedding layer that converts problem descriptions, solution descriptions, code snippets, and raw text into vectors for storage and search. This is the most critical component — embedding quality directly determines search quality.

## Embedding Model Selection

### Primary Models

| Vector Space | Model | Dimensions | Purpose | Size | Speed |
|---|---|---|---|---|---|
| `problem` | `sentence-transformers/all-MiniLM-L6-v2` | 384 | Natural language error descriptions | 80MB | ~14ms/text |
| `solution` | `sentence-transformers/all-MiniLM-L6-v2` | 384 | Solution descriptions | 80MB | ~14ms/text |
| `code_context` | `microsoft/codebert-base` | 768 | Code snippets, stack traces | 440MB | ~25ms/text |
| `keywords` (sparse) | Custom BM25 tokenizer | Variable | Exact token matching | <1MB | ~1ms/text |

### Why These Models

**all-MiniLM-L6-v2 (384d)**
- Best speed/quality tradeoff for general text
- 80MB — loads fast even on modest hardware
- Trained on 1B+ sentence pairs, strong semantic understanding
- Handles error messages well because they are natural language

**microsoft/codebert-base (768d)**
- Pre-trained on CodeSearchNet (6 languages, 2M code-comment pairs)
- Understands code syntax, variable names, function signatures
- Distinguishes between `data.map()` and `data.filter()` semantically
- Critical for code context search — a text model would fail here

**Custom BM25 Sparse Encoder**
- Captures exact tokens that dense models normalize away
- `ModuleNotFoundError` stays as `ModuleNotFoundError`, not "import error"
- `cv2` stays as `cv2`, not "computer vision library"
- Stack trace line numbers, class paths, version numbers — all preserved

### Alternative Models Considered

| Model | Dims | Why Not (for MVP) |
|---|---|---|
| `all-mpnet-base-v2` | 768 | Better quality but 2x slower, 3x larger. Upgrade path. |
| `BAAI/bge-small-en-v1.5` | 384 | Comparable to MiniLM. Good alternative. |
| `openai/clip-vit-base-patch32` | 512 | Multimodal — useful if we add screenshot support later |
| `Qwen3-VL-Embedding-2B` | 3584 | Massive — overkill for MVP, great for v2 multimodal |
| `nomic-embed-text-v1.5` | 768 | Strong Matryoshka model — good upgrade path |

## Implementation

### Core Embedding Service

```python
# src/context8/embeddings.py

from __future__ import annotations
import hashlib
from functools import lru_cache
from typing import Optional

import numpy as np
from sentence_transformers import SentenceTransformer


class EmbeddingService:
    """Manages all embedding models for Context8."""

    def __init__(
        self,
        text_model: str = "sentence-transformers/all-MiniLM-L6-v2",
        code_model: str = "microsoft/codebert-base",
        cache_size: int = 1024,
    ):
        self._text_model_name = text_model
        self._code_model_name = code_model
        self._text_model: Optional[SentenceTransformer] = None
        self._code_model: Optional[SentenceTransformer] = None
        self._cache_size = cache_size
        self._cache: dict[str, list[float]] = {}

    @property
    def text_model(self) -> SentenceTransformer:
        """Lazy-load text model on first use."""
        if self._text_model is None:
            self._text_model = SentenceTransformer(self._text_model_name)
        return self._text_model

    @property
    def code_model(self) -> SentenceTransformer:
        """Lazy-load code model on first use."""
        if self._code_model is None:
            self._code_model = SentenceTransformer(self._code_model_name)
        return self._code_model

    def _cache_key(self, text: str, model: str) -> str:
        return hashlib.md5(f"{model}:{text}".encode()).hexdigest()

    def embed_text(self, text: str) -> list[float]:
        """Embed natural language text (problems, solutions)."""
        key = self._cache_key(text, "text")
        if key in self._cache:
            return self._cache[key]

        embedding = self.text_model.encode(text, normalize_embeddings=True)
        result = embedding.tolist()

        if len(self._cache) < self._cache_size:
            self._cache[key] = result
        return result

    def embed_code(self, code: str) -> list[float]:
        """Embed code snippets and stack traces."""
        key = self._cache_key(code, "code")
        if key in self._cache:
            return self._cache[key]

        embedding = self.code_model.encode(code, normalize_embeddings=True)
        result = embedding.tolist()

        if len(self._cache) < self._cache_size:
            self._cache[key] = result
        return result

    def embed_sparse(self, text: str) -> tuple[list[int], list[float]]:
        """Generate BM25-style sparse vector from text.
        
        Returns (indices, values) for Actian SparseVector.
        """
        tokens = self._tokenize(text)
        term_freqs = {}
        for token in tokens:
            term_freqs[token] = term_freqs.get(token, 0) + 1

        # Convert to sparse vector format
        # Use hash of token as index (deterministic mapping to fixed vocab space)
        vocab_size = 30000  # sparse vector dimension space
        indices = []
        values = []

        for token, freq in sorted(term_freqs.items()):
            idx = hash(token) % vocab_size
            # BM25-style weight: tf / (tf + 1)
            weight = freq / (freq + 1.0)
            indices.append(idx)
            values.append(round(weight, 4))

        return indices, values

    def _tokenize(self, text: str) -> list[str]:
        """Simple tokenizer for sparse vectors.
        
        Preserves technical tokens that dense models normalize away:
        - Error class names: TypeError, ModuleNotFoundError
        - Library names: cv2, numpy, react-query
        - Version numbers: 5.x, 18.2.0
        - File paths: src/components/UserList.tsx
        """
        import re
        # Split on whitespace and punctuation, keep technical tokens
        tokens = re.findall(
            r'[A-Z][a-zA-Z]+Error'     # Error class names
            r'|[a-zA-Z_]\w*'           # identifiers
            r'|\d+\.\d+(?:\.\d+)?'     # version numbers
            r'|[a-zA-Z0-9_./\\-]+',    # paths and compound tokens
            text,
        )
        # Lowercase non-error tokens
        result = []
        for t in tokens:
            if t.endswith('Error') or t.endswith('Exception'):
                result.append(t)  # Preserve case for error types
            else:
                result.append(t.lower())
        return result

    def embed_record(self, problem_text: str, solution_text: str, code_snippet: str = "") -> dict:
        """Generate all vectors for a complete resolution record.
        
        Returns dict matching the named vector config:
        {
            "problem": [...],        # 384d
            "solution": [...],       # 384d
            "code_context": [...],   # 768d
            "keywords": SparseVector(indices=[...], values=[...])
        }
        """
        combined_text = f"{problem_text} {solution_text} {code_snippet}"
        sparse_indices, sparse_values = self.embed_sparse(combined_text)

        return {
            "problem": self.embed_text(problem_text),
            "solution": self.embed_text(solution_text),
            "code_context": self.embed_code(code_snippet) if code_snippet else self.embed_code(problem_text),
            "keywords_indices": sparse_indices,
            "keywords_values": sparse_values,
        }

    def embed_query(self, query_text: str, query_code: str = "") -> dict:
        """Generate query vectors for search.
        
        Returns vectors for each search strategy.
        """
        sparse_indices, sparse_values = self.embed_sparse(query_text + " " + query_code)

        return {
            "problem": self.embed_text(query_text),
            "code_context": self.embed_code(query_code) if query_code else self.embed_code(query_text),
            "keywords_indices": sparse_indices,
            "keywords_values": sparse_values,
        }
```

### BM25 Sparse Encoder Detail

The sparse encoder is intentionally simple but preserves the tokens that matter most for code errors:

```
Input: "TypeError: Cannot read properties of undefined (reading 'map')"

Tokenization:
  ["TypeError", "cannot", "read", "properties", "of", "undefined", "reading", "map"]

Sparse Vector:
  indices: [hash("TypeError")%30000, hash("cannot")%30000, ...]
  values:  [1.0, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5]
           (TypeError gets full weight as an Error token)
```

**Why not use a neural sparse encoder like SPLADE?**
- SPLADE is 440MB and slow to load
- For our use case, exact token matching is more important than learned sparse representations
- BM25-style is deterministic and interpretable
- We can always upgrade to SPLADE in v2

## Model Loading Strategy

Models are loaded lazily on first use. This is important because:

1. **Startup time** — Loading all models at server start adds 5-10 seconds. Lazy loading means the MCP server starts instantly.
2. **Memory** — If the agent only searches (no code context), CodeBERT never loads (saves 440MB).
3. **First-call latency** — The first embedding call pays the load cost (~2s for MiniLM, ~4s for CodeBERT). Subsequent calls are <20ms.

**Mitigation for first-call latency:**
```python
# Optional: preload models in background on server start
import threading

def preload_models(service: EmbeddingService):
    """Preload models in background thread."""
    service.text_model  # triggers lazy load
    service.code_model  # triggers lazy load

threading.Thread(target=preload_models, args=(embedding_service,), daemon=True).start()
```

## Testing Criteria

- [ ] `EmbeddingService` loads both models without errors
- [ ] `embed_text()` returns 384-dimensional vector for any text input
- [ ] `embed_code()` returns 768-dimensional vector for any code input
- [ ] `embed_sparse()` returns valid (indices, values) tuples
- [ ] Semantically similar texts have cosine similarity > 0.7
- [ ] Dissimilar texts have cosine similarity < 0.3
- [ ] Cache hit returns identical vector (no recomputation)
- [ ] `embed_record()` returns all required vector fields
- [ ] `embed_query()` returns all required query vectors

### Unit Tests

```python
# tests/test_embeddings.py

def test_text_embedding_dimensions():
    service = EmbeddingService()
    vec = service.embed_text("Hello world")
    assert len(vec) == 384

def test_code_embedding_dimensions():
    service = EmbeddingService()
    vec = service.embed_code("def hello(): return 'world'")
    assert len(vec) == 768

def test_semantic_similarity():
    service = EmbeddingService()
    v1 = service.embed_text("TypeError when accessing array")
    v2 = service.embed_text("Type error on array access")
    v3 = service.embed_text("How to cook pasta")
    
    sim_12 = cosine_similarity(v1, v2)
    sim_13 = cosine_similarity(v1, v3)
    
    assert sim_12 > 0.7  # Similar texts
    assert sim_13 < 0.3  # Dissimilar texts

def test_sparse_preserves_error_types():
    service = EmbeddingService()
    indices, values = service.embed_sparse("TypeError in component")
    # TypeError should be preserved as-is (case-sensitive)
    tokens = service._tokenize("TypeError in component")
    assert "TypeError" in tokens

def test_cache_hit():
    service = EmbeddingService()
    v1 = service.embed_text("test input")
    v2 = service.embed_text("test input")
    assert v1 == v2  # Same object from cache
```

## Performance Benchmarks (Expected)

| Operation | First Call | Cached | Batch (100) |
|-----------|-----------|--------|-------------|
| `embed_text()` | ~2.1s (model load) | ~14ms | ~200ms |
| `embed_code()` | ~4.2s (model load) | ~25ms | ~400ms |
| `embed_sparse()` | ~1ms | ~1ms | ~50ms |
| `embed_record()` | ~6.3s (first, both models) | ~40ms | ~650ms |
| `embed_query()` | ~2.1s (first) | ~15ms | N/A |

## Files Created

```
src/context8/
├── __init__.py
├── embeddings.py           # EmbeddingService class
└── tokenizer.py            # BM25 tokenizer (optional, can be in embeddings.py)

tests/
├── __init__.py
└── test_embeddings.py      # Unit tests
```

## Estimated Time: 1 hour

## Dependencies: Plan 01 (for testing against real DB)

## Next: Plan 03 (Storage Schema)
