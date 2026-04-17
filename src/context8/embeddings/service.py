from __future__ import annotations

import hashlib
import logging

from ..config import CODE_MODEL, TEXT_MODEL
from .tokenizer import BM25Tokenizer

logger = logging.getLogger("context8.embeddings")


class EmbeddingService:
    def __init__(
        self,
        text_model: str = TEXT_MODEL,
        code_model: str = CODE_MODEL,
        use_code_model: bool = False,
        cache_size: int = 1024,
    ):
        self._text_model_name = text_model
        self._code_model_name = code_model
        self._use_code_model = use_code_model
        self._text_model = None
        self._code_model = None
        self._cache: dict[str, list[float]] = {}
        self._cache_size = cache_size
        self._tokenizer = BM25Tokenizer()

    @property
    def text_model(self):
        if self._text_model is None:
            from sentence_transformers import SentenceTransformer

            logger.info(f"Loading text model: {self._text_model_name}")
            self._text_model = SentenceTransformer(self._text_model_name)
            logger.info("Text model loaded")
        return self._text_model

    @property
    def code_model(self):
        if self._code_model is None:
            if self._use_code_model:
                from sentence_transformers import SentenceTransformer

                logger.info(f"Loading code model: {self._code_model_name}")
                self._code_model = SentenceTransformer(self._code_model_name)
                logger.info("Code model loaded")
            else:
                return self.text_model
        return self._code_model

    def _cache_key(self, text: str, model_tag: str) -> str:
        return hashlib.md5(f"{model_tag}:{text[:500]}".encode()).hexdigest()

    def _get_cached(self, text: str, model_tag: str) -> list[float] | None:
        return self._cache.get(self._cache_key(text, model_tag))

    def _set_cached(self, text: str, model_tag: str, vector: list[float]) -> None:
        if len(self._cache) < self._cache_size:
            self._cache[self._cache_key(text, model_tag)] = vector

    def embed_text(self, text: str) -> list[float]:
        if not text.strip():
            return [0.0] * 384

        cached = self._get_cached(text, "text")
        if cached is not None:
            return cached

        embedding = self.text_model.encode(text, normalize_embeddings=True)
        result = embedding.tolist()
        self._set_cached(text, "text", result)
        return result

    def embed_code(self, code: str) -> list[float]:
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
        return self._tokenizer.encode(text)

    def embed_record(
        self,
        problem_text: str,
        solution_text: str,
        code_snippet: str = "",
    ) -> dict:
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
        logger.info("Warming up embedding models...")
        self.embed_text("warmup")
        if self._use_code_model:
            self.embed_code("def warmup(): pass")
        logger.info("Models warm")
