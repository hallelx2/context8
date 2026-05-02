from __future__ import annotations

import os
import platform
from pathlib import Path


def _env_truthy(name: str, default: str = "") -> bool:
    return os.environ.get(name, default).lower() in ("1", "true", "yes", "on")


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------
# Default is SQLite + sqlite-vec + FTS5 — zero infrastructure, single file
# at ~/.context8/context8.db. Set CONTEXT8_BACKEND=actian to use the
# original hackathon-era gRPC stack (install the actian-vectorai wheel from
# GitHub separately, then start the Docker container).
BACKEND = os.environ.get("CONTEXT8_BACKEND", "sqlite").strip().lower()


def _default_db_path() -> Path:
    return Path.home() / ".context8" / "context8.db"


DB_PATH = Path(os.environ.get("CONTEXT8_DB_PATH", str(_default_db_path())))

# Actian endpoint — only meaningful when BACKEND == "actian".
DB_HOST = os.environ.get("CONTEXT8_DB_HOST", "localhost")
DB_PORT = int(os.environ.get("CONTEXT8_DB_PORT", "50051"))
DB_URL = f"{DB_HOST}:{DB_PORT}"

COLLECTION_NAME = "context8_store"

TEXT_EMBED_DIM = 384
USE_CODE_MODEL = _env_truthy("CONTEXT8_USE_CODE_MODEL")
# CODE_EMBED_DIM matches the ACTIVE code model. Default is MiniLM (384d)
# since use_code_model=False reuses the text model. CodeBERT (768d) is
# opt-in via CONTEXT8_USE_CODE_MODEL=1.
_CODE_DIM_DEFAULT = "768" if USE_CODE_MODEL else "384"
CODE_EMBED_DIM = int(os.environ.get("CONTEXT8_CODE_EMBED_DIM", _CODE_DIM_DEFAULT))
SPARSE_VOCAB_SIZE = 30000

TEXT_MODEL = os.environ.get(
    "CONTEXT8_TEXT_MODEL",
    "sentence-transformers/all-MiniLM-L6-v2",
)
CODE_MODEL = os.environ.get(
    "CONTEXT8_CODE_MODEL",
    "microsoft/codebert-base",
)

DEFAULT_SEARCH_LIMIT = 5
MAX_SEARCH_LIMIT = 20
DEDUP_THRESHOLD = 0.95
SCORE_THRESHOLD = 0.0

DEFAULT_DENSE_WEIGHT = 0.50
DEFAULT_CODE_WEIGHT = 0.20
DEFAULT_SPARSE_WEIGHT = 0.30

COLD_START_THRESHOLD = 100

RECENCY_HALF_LIFE_DAYS = float(os.environ.get("CONTEXT8_RECENCY_HALF_LIFE_DAYS", "365"))
CONFIDENCE_BOOST_FLOOR = 0.7
WORKED_RATIO_BOOST_FLOOR = 0.6
WORKED_RATIO_MIN_SAMPLES = 3


def _home() -> Path:
    return Path.home()


def project_root() -> Path:
    here = Path(__file__).resolve().parent
    for ancestor in [here, here.parent, here.parent.parent, here.parent.parent.parent]:
        if (ancestor / "docker-compose.yml").exists():
            return ancestor
    return Path.cwd()


def _get_os() -> str:
    return platform.system().lower()


def claude_code_config_path() -> Path:
    return _home() / ".claude" / "settings.json"


def claude_desktop_config_path() -> Path:
    system = _get_os()
    if system == "darwin":
        return _home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    if system == "windows":
        appdata = os.environ.get("APPDATA", str(_home() / "AppData" / "Roaming"))
        return Path(appdata) / "Claude" / "claude_desktop_config.json"
    return _home() / ".config" / "Claude" / "claude_desktop_config.json"


def cursor_config_path() -> Path:
    return _home() / ".cursor" / "mcp.json"


def vscode_config_path() -> Path:
    return _home() / ".vscode" / "mcp.json"


def windsurf_config_path() -> Path:
    return _home() / ".windsurf" / "mcp.json"


def gemini_config_path() -> Path:
    return _home() / ".gemini" / "antigravity" / "mcp_config.json"


def continue_config_path() -> Path:
    return _home() / ".continue" / "config.json"


def get_server_command() -> list[str]:
    """Absolute command Claude Code (or any agent) should launch for the MCP server.

    Routes through the `serve` CLI so the auto-bootstrap (container, collection,
    models) runs before the stdio loop starts. Prefers the installed `context8`
    script on PATH; falls back to the current interpreter so the plugin works
    even when the entry-point script isn't globally available.
    """
    import shutil
    import sys

    script = shutil.which("context8")
    if script:
        return [script, "serve"]
    return [sys.executable, "-m", "context8", "serve"]


SUPPORTED_AGENTS = {
    "claude-code": {
        "name": "Claude Code",
        "config_path_fn": claude_code_config_path,
        "config_key": "mcpServers",
        "format": "claude-plugin",  # Uses plugin system, not settings.json
    },
    "claude-desktop": {
        "name": "Claude Desktop",
        "config_path_fn": claude_desktop_config_path,
        "config_key": "mcpServers",
        "format": "standard",
    },
    "cursor": {
        "name": "Cursor",
        "config_path_fn": cursor_config_path,
        "config_key": "mcpServers",
        "format": "standard",
    },
    "vscode": {
        "name": "VS Code (Copilot)",
        "config_path_fn": vscode_config_path,
        "config_key": "servers",
        "format": "vscode",
    },
    "windsurf": {
        "name": "Windsurf",
        "config_path_fn": windsurf_config_path,
        "config_key": "mcpServers",
        "format": "standard",
    },
    "gemini": {
        "name": "Gemini CLI",
        "config_path_fn": gemini_config_path,
        "config_key": "mcpServers",
        "format": "standard",
    },
}
