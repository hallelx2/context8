> _Historical hackathon artifact._ Context8 is now SQLite-first by default; the Actian backend is optional. See [README.md](../README.md) and [CLAUDE.md](../CLAUDE.md) for the current architecture.

# Plan 05 — Search Engine (Hybrid + Filtered + Named Vector Search)

## Objective

Build the search engine that combines dense semantic search, sparse keyword search, and metadata filtering to find the most relevant past solutions. This is the core value proposition of Context8 — and the core hackathon requirement.

## Search Architecture

```
                    User Query
                        │
                        ▼
              ┌─────────────────────┐
              │   Query Analyzer    │
              │                     │
              │ Detect query type:  │
              │ • Pure text         │
              │ • Error message     │
              │ • Code snippet      │
              │ • Mixed             │
              └─────────┬───────────┘
                        │
              ┌─────────▼───────────┐
              │  Embedding Layer    │
              │                     │
              │ Generate:           │
              │ • problem_vec 384d  │
              │ • code_ctx_vec 768d │
              │ • sparse_vec        │
              └─────────┬───────────┘
                        │
         ┌──────────────┼──────────────┐
         │              │              │
         ▼              ▼              ▼
   ┌──────────┐  ┌──────────┐  ┌──────────┐
   │  Dense   │  │  Dense   │  │  Sparse  │
   │  Search  │  │  Search  │  │  Search  │
   │ problem  │  │ code_ctx │  │ keywords │
   │ (384d)   │  │ (768d)   │  │ (BM25)   │
   └────┬─────┘  └────┬─────┘  └────┬─────┘
        │              │              │
        └──────────────┼──────────────┘
                       │
              ┌────────▼────────┐
              │ Metadata Filter │
              │                 │
              │ language = X    │
              │ framework = Y   │
              │ resolved = true │
              └────────┬────────┘
                       │
              ┌────────▼────────┐
              │  Hybrid Fusion  │
              │                 │
              │ RRF or DBSF     │
              │ with weights    │
              └────────┬────────┘
                       │
              ┌────────▼────────┐
              │  Post-process   │
              │                 │
              │ Dedup, rerank,  │
              │ format results  │
              └────────┬────────┘
                       │
                       ▼
                  Final Results
```

## Implementation

```python
# src/context8/search.py

from __future__ import annotations

from typing import Optional

from actian_vectorai import (
    Field,
    FilterBuilder,
    SearchParams,
    reciprocal_rank_fusion,
    distribution_based_score_fusion,
)

from .embeddings import EmbeddingService
from .storage import StorageService, COLLECTION_NAME
from .models import ResolutionRecord, SearchResult


class SearchEngine:
    """Hybrid search engine for Context8.
    
    Combines three search strategies:
    1. Dense search on "problem" vector (semantic similarity to error descriptions)
    2. Dense search on "code_context" vector (code-aware similarity)
    3. Sparse search on "keywords" vector (exact token matching — error codes, class names)
    
    Results are fused using Reciprocal Rank Fusion (RRF) and optionally
    filtered by metadata (language, framework, etc.)
    """

    def __init__(
        self,
        storage: StorageService,
        embeddings: EmbeddingService,
        fusion_method: str = "rrf",  # "rrf" or "dbsf"
        dense_weight: float = 0.5,
        code_weight: float = 0.2,
        sparse_weight: float = 0.3,
    ):
        self.storage = storage
        self.embeddings = embeddings
        self.fusion_method = fusion_method
        self.dense_weight = dense_weight
        self.code_weight = code_weight
        self.sparse_weight = sparse_weight

    def search(
        self,
        query: str,
        code_context: str = "",
        language: Optional[str] = None,
        framework: Optional[str] = None,
        error_type: Optional[str] = None,
        resolved_only: bool = True,
        limit: int = 5,
        score_threshold: float = 0.1,
    ) -> list[SearchResult]:
        """Execute hybrid search across all vector spaces.
        
        Args:
            query: Problem description or error message
            code_context: Optional code snippet for code-aware search
            language: Filter by programming language
            framework: Filter by framework
            error_type: Filter by error class name
            resolved_only: Only return confirmed solutions
            limit: Maximum results
            score_threshold: Minimum score cutoff
            
        Returns:
            List of SearchResult ordered by relevance
        """
        # Step 1: Generate query vectors
        query_vectors = self.embeddings.embed_query(query, code_context)

        # Step 2: Build metadata filter
        search_filter = self._build_filter(
            language=language,
            framework=framework,
            error_type=error_type,
            resolved_only=resolved_only,
        )

        # Step 3: Run parallel searches across vector spaces
        prefetch_limit = min(limit * 10, 50)  # Fetch more candidates for fusion

        # Dense search on "problem" vector space
        problem_results = self.storage.client.points.search(
            COLLECTION_NAME,
            vector=query_vectors["problem"],
            using="problem",
            filter=search_filter,
            limit=prefetch_limit,
            with_payload=True,
        )

        # Dense search on "code_context" vector space
        code_results = self.storage.client.points.search(
            COLLECTION_NAME,
            vector=query_vectors["code_context"],
            using="code_context",
            filter=search_filter,
            limit=prefetch_limit,
            with_payload=True,
        )

        # Sparse search on "keywords" vector space
        sparse_results = self.storage.client.points.search(
            COLLECTION_NAME,
            vector=query_vectors["keywords_values"],
            vector_name="keywords",
            sparse_indices=query_vectors["keywords_indices"],
            filter=search_filter,
            limit=prefetch_limit,
            with_payload=True,
        )

        # Step 4: Fuse results
        all_result_lists = [problem_results, code_results, sparse_results]
        weights = [self.dense_weight, self.code_weight, self.sparse_weight]

        if self.fusion_method == "rrf":
            fused = reciprocal_rank_fusion(
                all_result_lists,
                limit=limit,
                ranking_constant_k=60,
                weights=weights,
            )
        else:  # dbsf
            fused = distribution_based_score_fusion(
                all_result_lists,
                limit=limit,
            )

        # Step 5: Convert to SearchResult objects
        results = []
        for r in fused:
            if r.score < score_threshold:
                continue
            record = ResolutionRecord.from_payload(str(r.id), r.payload)
            results.append(SearchResult(
                record=record,
                score=r.score,
                match_type="hybrid",
            ))

        return results

    def search_by_problem(
        self,
        query: str,
        language: Optional[str] = None,
        limit: int = 5,
    ) -> list[SearchResult]:
        """Simple dense search on problem vector only.
        
        Use for quick lookups when hybrid search is overkill.
        """
        query_vec = self.embeddings.embed_text(query)
        
        search_filter = self._build_filter(language=language)
        
        results = self.storage.client.points.search(
            COLLECTION_NAME,
            vector=query_vec,
            using="problem",
            filter=search_filter,
            limit=limit,
            with_payload=True,
        )

        return [
            SearchResult(
                record=ResolutionRecord.from_payload(str(r.id), r.payload),
                score=r.score,
                match_type="dense",
            )
            for r in results
        ]

    def search_by_code(
        self,
        code_snippet: str,
        language: Optional[str] = None,
        limit: int = 5,
    ) -> list[SearchResult]:
        """Search by code context only.
        
        Use when the agent has code but no clear error message.
        """
        code_vec = self.embeddings.embed_code(code_snippet)
        
        search_filter = self._build_filter(language=language)
        
        results = self.storage.client.points.search(
            COLLECTION_NAME,
            vector=code_vec,
            using="code_context",
            filter=search_filter,
            limit=limit,
            with_payload=True,
        )

        return [
            SearchResult(
                record=ResolutionRecord.from_payload(str(r.id), r.payload),
                score=r.score,
                match_type="dense_code",
            )
            for r in results
        ]

    def find_duplicate(
        self,
        problem_text: str,
        threshold: float = 0.95,
    ) -> Optional[SearchResult]:
        """Check if a very similar problem already exists.
        
        Used before logging to prevent duplicates.
        """
        results = self.search_by_problem(problem_text, limit=1)
        if results and results[0].score >= threshold:
            return results[0]
        return None

    def _build_filter(
        self,
        language: Optional[str] = None,
        framework: Optional[str] = None,
        error_type: Optional[str] = None,
        resolved_only: bool = False,
    ):
        """Build Actian filter from search parameters."""
        conditions = []

        if language:
            conditions.append(Field("language").eq(language.lower()))
        if framework:
            conditions.append(Field("framework").eq(framework.lower()))
        if error_type:
            conditions.append(Field("error_type").eq(error_type))
        if resolved_only:
            conditions.append(Field("resolved").eq(True))

        if not conditions:
            return None

        builder = FilterBuilder()
        for condition in conditions:
            builder = builder.must(condition)
        return builder.build()


class QueryAnalyzer:
    """Analyze incoming queries to optimize search strategy.
    
    Determines:
    - Is this an error message? (lean toward sparse for exact tokens)
    - Is this code? (lean toward code_context vector)
    - Is this natural language? (lean toward problem vector)
    """

    @staticmethod
    def analyze(query: str, code_context: str = "") -> dict:
        """Return recommended search weights based on query type."""
        has_error_pattern = any(
            pattern in query
            for pattern in ["Error", "Exception", "Traceback", "error:", "FATAL", "panic"]
        )
        has_code = bool(code_context) or any(
            indicator in query
            for indicator in ["def ", "function ", "class ", "import ", "const ", "let ", "var "]
        )

        if has_error_pattern and has_code:
            # Error with code context — balance all three
            return {"dense": 0.35, "code": 0.30, "sparse": 0.35}
        elif has_error_pattern:
            # Pure error message — lean toward sparse (exact tokens matter)
            return {"dense": 0.40, "code": 0.15, "sparse": 0.45}
        elif has_code:
            # Pure code — lean toward code context
            return {"dense": 0.25, "code": 0.55, "sparse": 0.20}
        else:
            # Natural language query — lean toward dense semantic
            return {"dense": 0.60, "code": 0.15, "sparse": 0.25}
```

## Fusion Methods Explained

### Reciprocal Rank Fusion (RRF)

```
score(doc) = Σ weight_i / (k + rank_i(doc))
```

- `k = 60` (default) — dampening constant
- `rank_i(doc)` — rank of document in result list i
- `weight_i` — weight of result list i

**Why RRF for Context8:** RRF is rank-based, not score-based. This means it works well even when dense and sparse scores are on completely different scales (cosine similarity 0-1 vs BM25 scores 0-∞).

### Distribution-Based Score Fusion (DBSF)

Normalizes scores from each result list to a standard distribution before combining.

**When to use DBSF:** When all result lists are dense searches with similar score distributions. Less suitable when mixing dense + sparse.

**Recommendation:** Use RRF as default, offer DBSF as alternative.

## Search Weight Tuning

The default weights (`dense=0.5, code=0.2, sparse=0.3`) are starting points. Optimal weights depend on the query type:

| Query Type | Dense (problem) | Code Context | Sparse (keyword) |
|---|---|---|---|
| Error message | 0.40 | 0.15 | 0.45 |
| Error + code | 0.35 | 0.30 | 0.35 |
| Code only | 0.25 | 0.55 | 0.20 |
| Natural language | 0.60 | 0.15 | 0.25 |

The `QueryAnalyzer` auto-detects query type and adjusts weights.

## Testing Criteria

- [ ] `search()` returns results ranked by relevance
- [ ] Hybrid fusion outperforms any single search strategy (measured on test set)
- [ ] `_build_filter()` correctly constructs filters for all parameter combinations
- [ ] `find_duplicate()` catches near-identical records (threshold 0.95)
- [ ] `find_duplicate()` does NOT flag genuinely different problems
- [ ] QueryAnalyzer correctly classifies error messages, code, and natural language
- [ ] Results respect language/framework filters
- [ ] Empty query returns empty results (not an error)
- [ ] Score threshold correctly filters low-relevance results

### Integration Tests

```python
# tests/test_search.py

def test_hybrid_search_finds_similar_problem():
    """Seed a known problem, search with a variation, expect match."""
    # Seed: "TypeError when accessing undefined array in React"
    # Search: "Cannot read properties of undefined (reading 'map') in React component"
    # Expected: match with high score

def test_filtered_search_respects_language():
    """Seed Python + JS solutions, filter by Python, expect only Python results."""

def test_sparse_search_catches_exact_error_codes():
    """Seed 'ModuleNotFoundError: cv2', search same error, expect top result."""

def test_dedup_catches_near_identical():
    """Try to log same problem twice, second should be flagged as duplicate."""

def test_query_analyzer_classifies_correctly():
    assert QueryAnalyzer.analyze("TypeError: x is not a function")["sparse"] > 0.4
    assert QueryAnalyzer.analyze("def process_data(): ...")["code"] > 0.4
    assert QueryAnalyzer.analyze("how to fix slow database queries")["dense"] > 0.5
```

## Performance Targets

| Operation | Target | Notes |
|-----------|--------|-------|
| Single hybrid search | <200ms | After models loaded |
| Simple dense search | <50ms | Single vector space |
| Filter construction | <1ms | Pure Python logic |
| Fusion (RRF, 3 lists × 50 results) | <5ms | Client-side computation |

## Files Created

```
src/context8/
├── search.py         # SearchEngine + QueryAnalyzer
└── (extends existing files from previous plans)

tests/
├── test_search.py    # Search integration tests
└── test_query_analyzer.py  # Unit tests for query classification
```

## Estimated Time: 1.5 hours

## Dependencies: Plan 01, Plan 02, Plan 03

## Next: Plan 06 (Agent Integration)
