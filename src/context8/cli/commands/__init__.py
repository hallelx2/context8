from __future__ import annotations

from .bench import bench, demo
from .ingest import import_github, mine
from .integrations import add, remove
from .lifecycle import init, start, stop
from .ops import doctor, search_cmd, stats
from .serve import serve

__all__ = [
    "start",
    "stop",
    "init",
    "add",
    "remove",
    "stats",
    "doctor",
    "search_cmd",
    "bench",
    "demo",
    "import_github",
    "mine",
    "serve",
]
