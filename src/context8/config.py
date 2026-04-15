"""Context8 configuration constants and paths."""

from __future__ import annotations

import os
import platform
from pathlib import Path

# ── Database ──────────────────────────────────────────────────────────────────

DB_HOST = os.environ.get("CONTEXT8_DB_HOST", "localhost")
DB_PORT = int(os.environ.get("CONTEXT8_DB_PORT", "50051"))
DB_URL = f"{DB_HOST}:{DB_PORT}"

COLLECTION_NAME = "context8_store"

# ── Vector Dimensions ─────────────────────────────────────────────────────────

TEXT_EMBED_DIM = 384      # sentence-transformers/all-MiniLM-L6-v2
CODE_EMBED_DIM = 768      # microsoft/codebert-base
SPARSE_VOCAB_SIZE = 30000 # BM25 hash space

# ── Model Names ───────────────────────────────────────────────────────────────

TEXT_MODEL = os.environ.get(
    "CONTEXT8_TEXT_MODEL",
    "sentence-transformers/all-MiniLM-L6-v2",
)
CODE_MODEL = os.environ.get(
    "CONTEXT8_CODE_MODEL",
    "microsoft/codebert-base",
)

# ── Search Defaults ───────────────────────────────────────────────────────────

DEFAULT_SEARCH_LIMIT = 5
MAX_SEARCH_LIMIT = 20
DEDUP_THRESHOLD = 0.95
SCORE_THRESHOLD = 0.1

# Fusion weights (dense_problem, dense_code, sparse_keyword)
DEFAULT_DENSE_WEIGHT = 0.50
DEFAULT_CODE_WEIGHT = 0.20
DEFAULT_SPARSE_WEIGHT = 0.30

# ── Cold Start ────────────────────────────────────────────────────────────────

COLD_START_THRESHOLD = 100  # Exit cold-start mode after this many records

# ── Paths ─────────────────────────────────────────────────────────────────────

def _home() -> Path:
    return Path.home()


def project_root() -> Path:
    """Return the directory containing docker-compose.yml."""
    # Walk up from this file to find docker-compose.yml
    here = Path(__file__).resolve().parent
    for ancestor in [here, here.parent, here.parent.parent, here.parent.parent.parent]:
        if (ancestor / "docker-compose.yml").exists():
            return ancestor
    # Fallback: current working directory
    return Path.cwd()


# ── Agent Config Paths ────────────────────────────────────────────────────────

def _get_os() -> str:
    return platform.system().lower()


def claude_global_config_path() -> Path:
    """~/.claude/settings.json — Claude Code global MCP settings."""
    return _home() / ".claude" / "settings.json"


def claude_project_config_path() -> Path:
    """<project>/.claude/settings.json — Claude Code project-level MCP settings."""
    return Path.cwd() / ".claude" / "settings.json"


def cursor_config_path() -> Path:
    """<project>/.cursor/mcp.json — Cursor MCP settings."""
    return Path.cwd() / ".cursor" / "mcp.json"


def windsurf_config_path() -> Path:
    """<project>/.windsurf/mcp.json — Windsurf MCP settings."""
    return Path.cwd() / ".windsurf" / "mcp.json"


def continue_config_path() -> Path:
    """~/.continue/config.json — Continue MCP settings."""
    return _home() / ".continue" / "config.json"


# ── MCP Server Command ────────────────────────────────────────────────────────

def get_server_command() -> list[str]:
    """Return the command to start the Context8 MCP server."""
    return ["python", "-m", "context8.server"]


# ── Agent Registry ────────────────────────────────────────────────────────────

SUPPORTED_AGENTS = {
    "claude": {
        "name": "Claude Code",
        "config_path_fn": claude_global_config_path,
        "config_key": "mcpServers",
        "format": "claude",
    },
    "claude-project": {
        "name": "Claude Code (project)",
        "config_path_fn": claude_project_config_path,
        "config_key": "mcpServers",
        "format": "claude",
    },
    "cursor": {
        "name": "Cursor",
        "config_path_fn": cursor_config_path,
        "config_key": "mcpServers",
        "format": "cursor",
    },
    "windsurf": {
        "name": "Windsurf",
        "config_path_fn": windsurf_config_path,
        "config_key": "mcpServers",
        "format": "cursor",  # Same format as Cursor
    },
}
