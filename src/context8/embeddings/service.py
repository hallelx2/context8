from __future__ import annotations

import hashlib
import logging
import os

from ..config import CODE_EMBED_DIM, CODE_MODEL, TEXT_EMBED_DIM, TEXT_MODEL
from .tokenizer import BM25Tokenizer

logger = logging.getLogger("context8.embeddings")

_USE_CODE_MODEL_DEFAULT = os.environ.get("CONTEXT8_USE_CODE_MODEL", "").lower() in (
    "1",
    "true",
    "yes",
)


class EmbeddingService:
    def __init__(
        self,
        text_model: str = TEXT_MODEL,
        code_model: str = CODE_MODEL,
        use_code_model: bool = _USE_CODE_MODEL_DEFAULT,
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
        return hashlib.md5(f"{model_tag}:{text}".encode()).hexdigest()

    def _get_cached(self, text: str, model_tag: str) -> list[float] | None:
        return self._cache.get(self._cache_key(text, model_tag))

    def _set_cached(self, text: str, model_tag: str, vector: list[float]) -> None:
        if len(self._cache) < self._cache_size:
            self._cache[self._cache_key(text, model_tag)] = vector

    def embed_text(self, text: str) -> list[float]:
        if not text.strip():
            return [0.0] * TEXT_EMBED_DIM

        cached = self._get_cached(text, "text")
        if cached is not None:
            return cached

        embedding = self.text_model.encode(text, normalize_embeddings=True)
        result = embedding.tolist()
        self._set_cached(text, "text", result)
        return result

    def embed_code(self, code: str) -> list[float]:
        if not code.strip():
            dim = CODE_EMBED_DIM if self._use_code_model else TEXT_EMBED_DIM
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
        """Load models and run a dummy embedding to warm caches."""
        logger.info("Warming up embedding models...")
        self.embed_text("warmup")
        if self._use_code_model:
            self.embed_code("def warmup(): pass")
        logger.info("Models warm")

    @staticmethod
    def ensure_models_downloaded(text_model: str = "", code_model: str = "") -> None:
        """Pre-download embedding models if not already cached.

        Called during `context8 init` so the MCP server starts instantly.
        sentence-transformers caches models in ~/.cache/huggingface/hub/
        """
        from ..config import CODE_MODEL, TEXT_MODEL

        text_model = text_model or TEXT_MODEL
        code_model = code_model or CODE_MODEL

        from sentence_transformers import SentenceTransformer

        logger.info(f"Ensuring text model is downloaded: {text_model}")
        SentenceTransformer(text_model)
        logger.info("Text model ready")

        # Code model is opt-in — only pre-download if explicitly requested
        if code_model and code_model != text_model:
            logger.info(f"Code model available: {code_model} (downloaded on first use)")
