from __future__ import annotations

import re

from ..config import SPARSE_VOCAB_SIZE

_TOKEN_PATTERN = re.compile(
    r"[A-Z][a-zA-Z]*(?:Error|Exception)"
    r"|[a-zA-Z_][\w]*"
    r"|\d+\.\d+(?:\.\d+)?"
    r"|[a-zA-Z0-9_.\-/\\]+"
)


class BM25Tokenizer:
    def __init__(self, vocab_size: int = SPARSE_VOCAB_SIZE):
        self.vocab_size = vocab_size

    def tokenize(self, text: str) -> list[str]:
        result: list[str] = []
        for token in _TOKEN_PATTERN.findall(text):
            if token.endswith("Error") or token.endswith("Exception"):
                result.append(token)
            else:
                result.append(token.lower())
        return result

    def encode(self, text: str) -> tuple[list[int], list[float]]:
        if not text.strip():
            return [], []

        tokens = self.tokenize(text)
        if not tokens:
            return [], []

        term_freqs: dict[str, int] = {}
        for token in tokens:
            term_freqs[token] = term_freqs.get(token, 0) + 1

        indices: list[int] = []
        values: list[float] = []
        for token, freq in sorted(term_freqs.items()):
            idx = abs(hash(token)) % self.vocab_size
            weight = freq / (freq + 1.0)
            indices.append(idx)
            values.append(round(weight, 4))

        return indices, values
