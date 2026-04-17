from __future__ import annotations


class QueryAnalyzer:
    ERROR_PATTERNS = [
        "Error",
        "Exception",
        "Traceback",
        "FATAL",
        "panic",
        "error:",
        "ERR_",
        "E0",
        "TS2",
    ]
    CODE_PATTERNS = [
        "def ",
        "function ",
        "class ",
        "import ",
        "from ",
        "const ",
        "let ",
        "var ",
        "fn ",
        "pub ",
        "async ",
        "=>",
        "->",
        "::",
        "&&",
        "||",
    ]

    @classmethod
    def analyze(cls, query: str, code_context: str = "") -> dict:
        has_error = any(p in query for p in cls.ERROR_PATTERNS)
        has_code = bool(code_context) or any(p in query for p in cls.CODE_PATTERNS)

        if has_error and has_code:
            return {"dense": 0.35, "code": 0.30, "sparse": 0.35}
        if has_error:
            return {"dense": 0.40, "code": 0.15, "sparse": 0.45}
        if has_code:
            return {"dense": 0.25, "code": 0.55, "sparse": 0.20}
        return {"dense": 0.60, "code": 0.15, "sparse": 0.25}
