# Plan 08 — Testing Strategy

## Objective

Define the complete testing strategy for Context8, covering unit tests, integration tests, search quality evaluation, and end-to-end MCP protocol tests.

## Test Pyramid

```
         ┌─────────┐
         │  E2E    │  MCP protocol tests (agent ↔ server ↔ DB)
         │  (5)    │
        ─┼─────────┼─
        │ Integration│  Search quality, DB operations, embedding pipeline
        │   (15)     │
       ─┼────────────┼─
       │  Unit Tests  │  Models, tokenizer, query analyzer, config
       │    (25)      │
       └──────────────┘
```

## Unit Tests

### Test File: `tests/test_models.py`

```python
"""Unit tests for data models."""
import pytest
from context8.models import ResolutionRecord, SearchResult


class TestResolutionRecord:
    def test_create_minimal(self):
        record = ResolutionRecord(problem_text="test error")
        assert record.problem_text == "test error"
        assert record.id  # UUID generated
        assert record.timestamp  # auto-populated
        assert record.occurrence_count == 1

    def test_to_payload_roundtrip(self):
        original = ResolutionRecord(
            problem_text="TypeError in component",
            solution_text="Added null check",
            language="typescript",
            framework="react",
            tags=["null-check", "typescript"],
            confidence=0.92,
        )
        payload = original.to_payload()
        restored = ResolutionRecord.from_payload(original.id, payload)
        
        assert restored.problem_text == original.problem_text
        assert restored.solution_text == original.solution_text
        assert restored.language == original.language
        assert restored.tags == original.tags
        assert restored.confidence == original.confidence

    def test_payload_contains_all_fields(self):
        record = ResolutionRecord(problem_text="test")
        payload = record.to_payload()
        
        required_fields = [
            "problem_text", "solution_text", "error_type",
            "language", "framework", "tags", "libraries",
            "resolved", "confidence", "timestamp",
        ]
        for field in required_fields:
            assert field in payload, f"Missing field: {field}"

    def test_default_values(self):
        record = ResolutionRecord(problem_text="test")
        assert record.resolved is True
        assert record.confidence == 0.5
        assert record.source == "local"
        assert record.os == ""
```

### Test File: `tests/test_query_analyzer.py`

```python
"""Unit tests for query analysis."""
import pytest
from context8.search import QueryAnalyzer


class TestQueryAnalyzer:
    def test_error_message_detection(self):
        weights = QueryAnalyzer.analyze("TypeError: x is not a function")
        assert weights["sparse"] >= 0.4  # Error tokens matter

    def test_code_detection(self):
        weights = QueryAnalyzer.analyze("def process_data(items): return [x for x in items]")
        assert weights["code"] >= 0.4  # Code context matters

    def test_natural_language(self):
        weights = QueryAnalyzer.analyze("how to fix slow database queries")
        assert weights["dense"] >= 0.5  # Semantic meaning matters

    def test_mixed_error_and_code(self):
        weights = QueryAnalyzer.analyze(
            "TypeError in component",
            code_context="const items = data.map(x => x.name)"
        )
        # All three should be balanced
        assert weights["dense"] >= 0.2
        assert weights["code"] >= 0.2
        assert weights["sparse"] >= 0.2

    def test_weights_sum_to_one(self):
        for query in [
            "TypeError: x is not a function",
            "def foo(): pass",
            "how to fix this",
            "error in const x = data.map()",
        ]:
            weights = QueryAnalyzer.analyze(query)
            total = weights["dense"] + weights["code"] + weights["sparse"]
            assert abs(total - 1.0) < 0.01, f"Weights sum to {total}, not 1.0"
```

### Test File: `tests/test_tokenizer.py`

```python
"""Unit tests for BM25 sparse tokenizer."""
import pytest
from context8.embeddings import EmbeddingService


class TestTokenizer:
    def setup_method(self):
        self.svc = EmbeddingService.__new__(EmbeddingService)

    def test_preserves_error_types(self):
        tokens = self.svc._tokenize("TypeError: x is not defined")
        assert "TypeError" in tokens

    def test_preserves_version_numbers(self):
        tokens = self.svc._tokenize("react@18.2.0 has a bug")
        assert any("18.2.0" in t for t in tokens)

    def test_lowercase_normal_tokens(self):
        tokens = self.svc._tokenize("The Quick Brown Fox")
        assert "the" in tokens or "quick" in tokens

    def test_preserves_exception_classes(self):
        tokens = self.svc._tokenize("ModuleNotFoundError when importing cv2")
        assert "ModuleNotFoundError" in tokens

    def test_sparse_vector_format(self):
        indices, values = self.svc.embed_sparse("test input text")
        assert len(indices) == len(values)
        assert all(isinstance(i, int) for i in indices)
        assert all(isinstance(v, float) for v in values)
        assert all(0 < v <= 1.0 for v in values)
```

## Integration Tests

### Test File: `tests/test_storage_integration.py`

**Requires running Actian VectorAI DB Docker container.**

```python
"""Integration tests for storage layer."""
import pytest
from context8.storage import StorageService, COLLECTION_NAME
from context8.models import ResolutionRecord
from context8.embeddings import EmbeddingService


@pytest.fixture(scope="module")
def storage():
    svc = StorageService()
    # Use a test collection
    svc.initialize()
    yield svc
    # Cleanup
    if svc.client.collections.exists(COLLECTION_NAME):
        svc.client.collections.delete(COLLECTION_NAME)
    svc.close()


@pytest.fixture(scope="module")
def embeddings():
    return EmbeddingService()


class TestStorageIntegration:
    def test_collection_created(self, storage):
        assert storage.client.collections.exists(COLLECTION_NAME)

    def test_store_and_retrieve(self, storage, embeddings):
        record = ResolutionRecord(
            problem_text="Test error for integration test",
            solution_text="This is the test solution",
            language="python",
        )
        vectors = embeddings.embed_record(
            record.problem_text,
            record.solution_text,
        )
        
        record_id = storage.store_record(record, vectors)
        assert record_id == record.id
        
        retrieved = storage.get_record(record_id)
        assert retrieved is not None
        assert retrieved.problem_text == "Test error for integration test"

    def test_count(self, storage):
        count = storage.count()
        assert count >= 1  # At least the record from previous test

    def test_delete(self, storage, embeddings):
        record = ResolutionRecord(
            problem_text="Record to delete",
            solution_text="Will be deleted",
        )
        vectors = embeddings.embed_record(record.problem_text, record.solution_text)
        storage.store_record(record, vectors)
        
        storage.delete_record(record.id)
        retrieved = storage.get_record(record.id)
        assert retrieved is None
```

### Test File: `tests/test_search_integration.py`

```python
"""Integration tests for search engine."""
import pytest
from context8.search import SearchEngine
from context8.storage import StorageService
from context8.embeddings import EmbeddingService
from context8.models import ResolutionRecord


@pytest.fixture(scope="module")
def engine():
    storage = StorageService()
    storage.initialize()
    embeddings = EmbeddingService()
    engine = SearchEngine(storage, embeddings)
    
    # Seed test data
    test_records = [
        ResolutionRecord(
            problem_text="TypeError: Cannot read properties of undefined (reading 'map')",
            solution_text="Added optional chaining: data?.items ?? []",
            language="typescript",
            framework="react",
            error_type="TypeError",
            tags=["undefined", "optional-chaining"],
        ),
        ResolutionRecord(
            problem_text="ModuleNotFoundError: No module named 'cv2'",
            solution_text="Install opencv-python-headless in the correct venv",
            language="python",
            error_type="ModuleNotFoundError",
            tags=["opencv", "import"],
        ),
    ]
    
    for record in test_records:
        vectors = embeddings.embed_record(record.problem_text, record.solution_text)
        storage.store_record(record, vectors)
    
    yield engine
    
    # Cleanup handled by storage fixture


class TestSearchIntegration:
    def test_semantic_search_finds_similar(self, engine):
        results = engine.search("undefined error when mapping array in React")
        assert len(results) > 0
        assert "TypeError" in results[0].record.error_type or "map" in results[0].record.problem_text

    def test_language_filter(self, engine):
        results = engine.search("import error", language="python")
        for r in results:
            assert r.record.language == "python"

    def test_dedup_detection(self, engine):
        dup = engine.find_duplicate("TypeError: Cannot read properties of undefined (reading 'map')")
        assert dup is not None
        assert dup.score >= 0.90

    def test_no_results_for_unrelated(self, engine):
        results = engine.search("how to bake chocolate cake", limit=3)
        # Should return empty or very low scores
        assert len(results) == 0 or results[0].score < 0.3
```

## Search Quality Evaluation

### Ground Truth Test

```python
# tests/test_ground_truth.py

"""Evaluate search quality against ground truth."""
import pytest
from context8.search import SearchEngine
from context8.seed import seed_database


GROUND_TRUTH = [
    {"query": "python module not found cv2 opencv", "expected_tags": ["opencv"]},
    {"query": "pip install error externally managed ubuntu", "expected_tags": ["pip", "pep668"]},
    {"query": "npm dependency tree conflict peer deps", "expected_tags": ["npm", "peer-deps"]},
    {"query": "react hydration mismatch server client", "expected_tags": ["hydration"]},
    {"query": "docker volume empty windows wsl", "expected_tags": ["volume"]},
    {"query": "typescript type never array conditional", "expected_tags": ["never"]},
    {"query": "git merge conflict package-lock.json", "expected_tags": ["lockfile"]},
    {"query": "windows path too long node_modules enoent", "expected_tags": ["long-path"]},
    {"query": "vite cache stale not a function", "expected_tags": ["vite", "prebundling"]},
    {"query": "postgres connection pool exhausted serverless prisma", "expected_tags": ["connection-pool"]},
]


def test_recall_at_3(engine_with_seed_data):
    """At least 80% of ground truth queries should find the right answer in top 3."""
    hits = 0
    
    for gt in GROUND_TRUTH:
        results = engine_with_seed_data.search(gt["query"], limit=3)
        
        found = False
        for r in results:
            if any(tag in r.record.tags for tag in gt["expected_tags"]):
                found = True
                break
        
        if found:
            hits += 1

    recall = hits / len(GROUND_TRUTH)
    assert recall >= 0.8, f"Recall@3 = {recall:.2f}, expected >= 0.80"


def test_precision_at_3(engine_with_seed_data):
    """At least 60% of top-3 results should be actually relevant."""
    total_results = 0
    relevant_results = 0
    
    for gt in GROUND_TRUTH:
        results = engine_with_seed_data.search(gt["query"], limit=3)
        
        for r in results:
            total_results += 1
            if any(tag in r.record.tags for tag in gt["expected_tags"]):
                relevant_results += 1

    precision = relevant_results / max(total_results, 1)
    assert precision >= 0.6, f"Precision@3 = {precision:.2f}, expected >= 0.60"
```

## End-to-End Tests

### Test File: `tests/test_e2e.py`

```python
"""End-to-end tests: MCP protocol ↔ server ↔ DB."""
import pytest
import asyncio
from context8.server import call_tool


class TestE2E:
    @pytest.mark.asyncio
    async def test_log_then_search(self):
        """Log a solution, then search for it."""
        # Log
        log_result = await call_tool("context8_log", {
            "problem": "E2E test: unique error XYZ-12345 in foobar module",
            "solution": "E2E test: fixed by adjusting the foobar config",
            "language": "python",
            "tags": ["e2e-test"],
            "confidence": 0.99,
        })
        assert "logged" in log_result[0].text.lower() or "Record ID" in log_result[0].text

        # Search
        search_result = await call_tool("context8_search", {
            "query": "XYZ-12345 error in foobar",
            "language": "python",
            "limit": 3,
        })
        assert "foobar" in search_result[0].text

    @pytest.mark.asyncio
    async def test_stats(self):
        """Stats tool returns valid response."""
        result = await call_tool("context8_stats", {})
        assert "Total records" in result[0].text
        assert "HEALTHY" in result[0].text

    @pytest.mark.asyncio
    async def test_search_no_results(self):
        """Search for something that doesn't exist."""
        result = await call_tool("context8_search", {
            "query": "completely unique nonsense query zxcvbnm98765",
        })
        assert "no matching" in result[0].text.lower() or "0" in result[0].text
```

## Running Tests

```bash
# Unit tests (no Docker needed)
pytest tests/test_models.py tests/test_query_analyzer.py tests/test_tokenizer.py -v

# Integration tests (Docker required)
docker compose up -d
pytest tests/test_storage_integration.py tests/test_search_integration.py -v

# Ground truth evaluation
python -m context8 --seed
pytest tests/test_ground_truth.py -v

# E2E tests
pytest tests/test_e2e.py -v

# All tests
pytest tests/ -v --tb=short
```

## Test Configuration

```python
# tests/conftest.py

import pytest
from context8.storage import StorageService
from context8.embeddings import EmbeddingService
from context8.search import SearchEngine


@pytest.fixture(scope="session")
def storage_service():
    svc = StorageService()
    svc.initialize()
    yield svc
    svc.close()


@pytest.fixture(scope="session")
def embedding_service():
    return EmbeddingService()


@pytest.fixture(scope="session")
def search_engine(storage_service, embedding_service):
    return SearchEngine(storage_service, embedding_service)
```

## Coverage Targets

| Component | Target Coverage | Priority |
|-----------|----------------|----------|
| `models.py` | 95% | High |
| `search.py` | 85% | High |
| `embeddings.py` | 80% | Medium |
| `storage.py` | 80% | Medium |
| `server.py` | 75% | Medium |
| `seed.py` | 70% | Low |

## Estimated Time: 1.5 hours

## Dependencies: Plans 01-07

## Next: BOTTLENECKS.md
