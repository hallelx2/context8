"""Embedding pipeline for Context8.

Generates dense and sparse vectors from problem descriptions,
solution descriptions, and code snippets.
"""

from __future__ import annotations

import hashlib
import logging
import re

from .config import CODE_MODEL, SPARSE_VOCAB_SIZE, TEXT_MODEL

logger = logging.getLogger("context8.embeddings")


class EmbeddingService:
    """Manages embedding models for Context8.

    Models are loaded lazily on first use to avoid slow startup.
    A simple in-memory cache prevents re-embedding identical inputs.
    """

    def __init__(
        self,
        text_model: str = TEXT_MODEL,
        code_model: str = CODE_MODEL,
        use_code_model: bool = False,  # Opt-in for CodeBERT (saves ~880MB RAM)
        cache_size: int = 1024,
    ):
        self._text_model_name = text_model
        self._code_model_name = code_model
        self._use_code_model = use_code_model
        self._text_model = None
        self._code_model = None
        self._cache: dict[str, list[float]] = {}
        self._cache_size = cache_size

    @property
    def text_model(self):
        """Lazy-load text model on first use."""
        if self._text_model is None:
            from sentence_transformers import SentenceTransformer

            logger.info(f"Loading text model: {self._text_model_name}")
            self._text_model = SentenceTransformer(self._text_model_name)
            logger.info("Text model loaded")
        return self._text_model

    @property
    def code_model(self):
        """Lazy-load code model on first use."""
        if self._code_model is None:
            if self._use_code_model:
                from sentence_transformers import SentenceTransformer

                logger.info(f"Loading code model: {self._code_model_name}")
                self._code_model = SentenceTransformer(self._code_model_name)
                logger.info("Code model loaded")
            else:
                # Reuse text model for code (saves memory)
                return self.text_model
        return self._code_model

    def _cache_key(self, text: str, model_tag: str) -> str:
        return hashlib.md5(f"{model_tag}:{text[:500]}".encode()).hexdigest()

    def _get_cached(self, text: str, model_tag: str) -> list[float] | None:
        key = self._cache_key(text, model_tag)
        return self._cache.get(key)

    def _set_cached(self, text: str, model_tag: str, vector: list[float]) -> None:
        if len(self._cache) < self._cache_size:
            key = self._cache_key(text, model_tag)
            self._cache[key] = vector

    def embed_text(self, text: str) -> list[float]:
        """Embed natural language text (problems, solutions)."""
        if not text.strip():
            # Return zero vector for empty input
            return [0.0] * 384

        cached = self._get_cached(text, "text")
        if cached is not None:
            return cached

        embedding = self.text_model.encode(text, normalize_embeddings=True)
        result = embedding.tolist()
        self._set_cached(text, "text", result)
        return result

    def embed_code(self, code: str) -> list[float]:
        """Embed code snippets and stack traces."""
        if not code.strip():
            dim = 768 if self._use_code_model else 384
            return [0.0] * dim

        cached = self._get_cached(code, "code")
        if cached is not None:
            return cached

        embedding = self.code_model.encode(code, normalize_embeddings=True)
        result = embedding.tolist()
        self._set_cached(code, "code", result)
        return result

    def embed_sparse(self, text: str) -> tuple[list[int], list[float]]:
        """Generate BM25-style sparse vector from text.

        Returns (indices, values) for Actian SparseVector.
        Preserves technical tokens that dense models normalize away:
        error class names, library names, version numbers.
        """
        if not text.strip():
            return [], []

        tokens = self._tokenize(text)
        if not tokens:
            return [], []

        # Count term frequencies
        term_freqs: dict[str, int] = {}
        for token in tokens:
            term_freqs[token] = term_freqs.get(token, 0) + 1

        # Convert to sparse vector
        indices = []
        values = []
        for token, freq in sorted(term_freqs.items()):
            idx = abs(hash(token)) % SPARSE_VOCAB_SIZE
            # BM25-inspired weight: tf / (tf + 1) — saturates for repeated terms
            weight = freq / (freq + 1.0)
            indices.append(idx)
            values.append(round(weight, 4))

        return indices, values

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text preserving technical tokens.

        Keeps intact:
        - Error class names: TypeError, ModuleNotFoundError
        - Version numbers: 18.2.0, 5.x
        - File paths: src/components/UserList.tsx
        - Library names: react-query, opencv-python
        """
        tokens = re.findall(
            r"[A-Z][a-zA-Z]*(?:Error|Exception)"  # Error/Exception classes
            r"|[a-zA-Z_][\w]*"  # identifiers
            r"|\d+\.\d+(?:\.\d+)?"  # version numbers
            r"|[a-zA-Z0-9_.\-/\\]+",  # paths and compound tokens
            text,
        )
        result = []
        for t in tokens:
            if t.endswith("Error") or t.endswith("Exception"):
                result.append(t)  # Preserve case for error types
            else:
                result.append(t.lower())
        return result

    def embed_record(
        self,
        problem_text: str,
        solution_text: str,
        code_snippet: str = "",
    ) -> dict:
        """Generate all vectors for a complete resolution record.

        Returns dict with keys matching the collection's named vectors:
            problem: list[float] (384d)
            solution: list[float] (384d)
            code_context: list[float] (768d or 384d)
            keywords_indices: list[int]
            keywords_values: list[float]
        """
        combined_text = f"{problem_text} {solution_text} {code_snippet}"
        sparse_indices, sparse_values = self.embed_sparse(combined_text)

        code_input = code_snippet if code_snippet else problem_text

        return {
            "problem": self.embed_text(problem_text),
            "solution": self.embed_text(solution_text),
            "code_context": self.embed_code(code_input),
            "keywords_indices": sparse_indices,
            "keywords_values": sparse_values,
        }

    def embed_query(self, query_text: str, query_code: str = "") -> dict:
        """Generate query vectors for search.

        Returns vectors for each search strategy.
        """
        combined = f"{query_text} {query_code}".strip()
        sparse_indices, sparse_values = self.embed_sparse(combined)

        code_input = query_code if query_code else query_text

        return {
            "problem": self.embed_text(query_text),
            "code_context": self.embed_code(code_input),
            "keywords_indices": sparse_indices,
            "keywords_values": sparse_values,
        }

    def warmup(self) -> None:
        """Preload models by running a dummy embedding."""
        logger.info("Warming up embedding models...")
        self.embed_text("warmup")
        if self._use_code_model:
            self.embed_code("def warmup(): pass")
        logger.info("Models warm")
