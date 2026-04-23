from __future__ import annotations

import os
import platform
from pathlib import Path

DB_HOST = os.environ.get("CONTEXT8_DB_HOST", "localhost")
DB_PORT = int(os.environ.get("CONTEXT8_DB_PORT", "50051"))
DB_URL = f"{DB_HOST}:{DB_PORT}"

COLLECTION_NAME = "context8_store"

TEXT_EMBED_DIM = 384
# CODE_EMBED_DIM matches the ACTIVE code model. Default is MiniLM (384d)
# since use_code_model=False reuses the text model. Set to 768 only if
# CONTEXT8_USE_CODE_MODEL=1 and using CodeBERT.
CODE_EMBED_DIM = int(os.environ.get("CONTEXT8_CODE_EMBED_DIM", "384"))
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
SCORE_THRESHOLD = 0.1

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
    return ["python", "-m", "context8.mcp.server"]


SUPPORTED_AGENTS = {
    "claude-code": {
        "name": "Claude Code",
        "config_path_fn": claude_code_config_path,
        "config_key": "mcpServers",
        "format": "standard",
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
