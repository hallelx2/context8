"""Unit tests for the BM25 sparse tokenizer — no model downloads needed."""

from __future__ import annotations

from context8.embeddings import EmbeddingService


class TestTokenizer:
    """Test the BM25 tokenizer without loading any ML models."""

    def setup_method(self):
        # Create instance without triggering model downloads
        self.svc = EmbeddingService.__new__(EmbeddingService)

    def test_preserves_error_types(self):
        tokens = self.svc._tokenize("TypeError: x is not defined")
        assert "TypeError" in tokens

    def test_preserves_exception_classes(self):
        tokens = self.svc._tokenize("ModuleNotFoundError when importing cv2")
        assert "ModuleNotFoundError" in tokens

    def test_lowercase_normal_tokens(self):
        tokens = self.svc._tokenize("The Quick Brown Fox")
        lowered = [t for t in tokens if t.islower()]
        assert len(lowered) > 0

    def test_preserves_version_numbers(self):
        tokens = self.svc._tokenize("react@18.2.0 has a bug")
        assert any("18.2.0" in t for t in tokens)

    def test_empty_input(self):
        indices, values = self.svc.embed_sparse("")
        assert indices == []
        assert values == []

    def test_sparse_vector_format(self):
        self.svc._cache = {}
        self.svc._cache_size = 0
        indices, values = self.svc.embed_sparse("test input text for sparse")
        assert len(indices) == len(values)
        assert all(isinstance(i, int) for i in indices)
        assert all(isinstance(v, float) for v in values)
        assert all(0 < v <= 1.0 for v in values)

    def test_sparse_indices_in_vocab_range(self):
        self.svc._cache = {}
        self.svc._cache_size = 0
        indices, _ = self.svc.embed_sparse("TypeError in module foo.bar")
        for idx in indices:
            assert 0 <= idx < 30000


class TestQueryAnalyzer:
    """Test query type classification."""

    def test_error_message_detection(self):
        from context8.search import QueryAnalyzer

        weights = QueryAnalyzer.analyze("TypeError: x is not a function")
        assert weights["sparse"] >= 0.4

    def test_code_detection(self):
        from context8.search import QueryAnalyzer

        weights = QueryAnalyzer.analyze("broken function", code_context="def process(items): pass")
        assert weights["code"] >= 0.2

    def test_natural_language(self):
        from context8.search import QueryAnalyzer

        weights = QueryAnalyzer.analyze("how to fix slow database queries")
        assert weights["dense"] >= 0.5

    def test_weights_sum_to_one(self):
        from context8.search import QueryAnalyzer

        for query in [
            "TypeError: x is not a function",
            "def foo(): pass",
            "how to fix this",
        ]:
            weights = QueryAnalyzer.analyze(query)
            total = weights["dense"] + weights["code"] + weights["sparse"]
            assert abs(total - 1.0) < 0.01, f"Weights sum to {total}"
