from __future__ import annotations

import json
from pathlib import Path

from .config import DB_HOST, DB_PORT, SUPPORTED_AGENTS, get_server_command

# ── Plugin directory (Claude Code) ────────────────────────────────────────────

CLAUDE_PLUGIN_DIR = (
    Path.home()
    / ".claude"
    / "plugins"
    / "marketplaces"
    / "claude-plugins-official"
    / "external_plugins"
    / "context8"
)

PLUGIN_MANIFEST = {
    "name": "context8",
    "description": (
        "Collective problem-solving memory for coding agents. "
        "Search and log uncommon errors, workarounds, and agent-discovered "
        "fixes backed by Actian VectorAI DB."
    ),
    "author": {"name": "Context8 Team"},
}


# ── Helpers ───────────────────────────────────────────────────────────────────


def _build_mcp_entry(fmt: str) -> dict:
    cmd = get_server_command()

    if fmt == "vscode":
        return {
            "command": cmd[0],
            "args": cmd[1:],
            "type": "stdio",
        }

    return {
        "command": cmd[0],
        "args": cmd[1:],
        "env": {
            "CONTEXT8_DB_HOST": DB_HOST,
            "CONTEXT8_DB_PORT": str(DB_PORT),
        },
    }


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            return {}
        return json.loads(text)
    except (json.JSONDecodeError, OSError):
        return {}


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


# ── Claude Code plugin install/remove ─────────────────────────────────────────


def _add_claude_code_plugin() -> tuple[bool, str]:
    """Install Context8 as a Claude Code plugin.

    Writes two files into the plugin directory:
      .claude-plugin/plugin.json  — plugin manifest
      .mcp.json                   — MCP server config
    """
    plugin_dir = CLAUDE_PLUGIN_DIR
    manifest_dir = plugin_dir / ".claude-plugin"
    manifest_path = manifest_dir / "plugin.json"
    mcp_path = plugin_dir / ".mcp.json"

    if mcp_path.exists():
        return True, f"Context8 plugin already installed ({plugin_dir})"

    manifest_dir.mkdir(parents=True, exist_ok=True)
    _write_json(manifest_path, PLUGIN_MANIFEST)

    mcp_entry = _build_mcp_entry("standard")
    _write_json(mcp_path, {"context8": mcp_entry})

    return True, f"Installed Context8 plugin\n  Dir: {plugin_dir}"


def _remove_claude_code_plugin() -> tuple[bool, str]:
    """Remove Context8 from Claude Code plugins."""
    plugin_dir = CLAUDE_PLUGIN_DIR
    mcp_path = plugin_dir / ".mcp.json"
    manifest_path = plugin_dir / ".claude-plugin" / "plugin.json"

    if not mcp_path.exists():
        return True, "Context8 plugin is not installed — nothing to remove"

    mcp_path.unlink(missing_ok=True)
    manifest_path.unlink(missing_ok=True)

    # Clean up empty dirs
    claude_plugin_dir = plugin_dir / ".claude-plugin"
    if claude_plugin_dir.exists() and not any(claude_plugin_dir.iterdir()):
        claude_plugin_dir.rmdir()
    if plugin_dir.exists() and not any(plugin_dir.iterdir()):
        plugin_dir.rmdir()

    return True, "Removed Context8 plugin from Claude Code"


def _check_claude_code_plugin() -> bool:
    """Check if Context8 is installed as a Claude Code plugin."""
    return (CLAUDE_PLUGIN_DIR / ".mcp.json").exists()


# ── Generic add/remove (JSON-based agents) ────────────────────────────────────


def add_to_agent(agent_key: str) -> tuple[bool, str]:
    if agent_key not in SUPPORTED_AGENTS:
        supported = ", ".join(sorted(SUPPORTED_AGENTS.keys()))
        return False, f"Unknown agent '{agent_key}'. Supported: {supported}"

    agent = SUPPORTED_AGENTS[agent_key]

    # Claude Code uses the plugin system, not settings.json
    if agent.get("format") == "claude-plugin":
        return _add_claude_code_plugin()

    config_path: Path = agent["config_path_fn"]()
    config_key: str = agent["config_key"]
    fmt: str = agent["format"]
    agent_name: str = agent["name"]

    config = _read_json(config_path)
    if config_key not in config:
        config[config_key] = {}

    if "context8" in config[config_key]:
        return True, f"Context8 is already configured in {agent_name} ({config_path})"

    config[config_key]["context8"] = _build_mcp_entry(fmt)
    _write_json(config_path, config)
    return True, f"Added Context8 to {agent_name}\n  Config: {config_path}"


def remove_from_agent(agent_key: str) -> tuple[bool, str]:
    if agent_key not in SUPPORTED_AGENTS:
        supported = ", ".join(sorted(SUPPORTED_AGENTS.keys()))
        return False, f"Unknown agent '{agent_key}'. Supported: {supported}"

    agent = SUPPORTED_AGENTS[agent_key]

    if agent.get("format") == "claude-plugin":
        return _remove_claude_code_plugin()

    config_path: Path = agent["config_path_fn"]()
    config_key: str = agent["config_key"]
    agent_name: str = agent["name"]

    config = _read_json(config_path)
    if config_key not in config or "context8" not in config.get(config_key, {}):
        return True, f"Context8 is not configured in {agent_name} — nothing to remove"

    del config[config_key]["context8"]
    if not config[config_key]:
        del config[config_key]

    _write_json(config_path, config)
    return True, f"Removed Context8 from {agent_name}\n  Config: {config_path}"


def check_agent(agent_key: str) -> tuple[bool, str]:
    if agent_key not in SUPPORTED_AGENTS:
        return False, f"Unknown agent '{agent_key}'"

    agent = SUPPORTED_AGENTS[agent_key]

    if agent.get("format") == "claude-plugin":
        installed = _check_claude_code_plugin()
        if installed:
            return True, f"Context8 plugin installed ({CLAUDE_PLUGIN_DIR})"
        return False, "Context8 plugin is NOT installed in Claude Code"

    config_path: Path = agent["config_path_fn"]()
    config_key: str = agent["config_key"]
    agent_name: str = agent["name"]

    config = _read_json(config_path)
    is_configured = "context8" in config.get(config_key, {})

    if is_configured:
        return True, f"Context8 is configured in {agent_name} ({config_path})"
    return False, f"Context8 is NOT configured in {agent_name}"


def list_agents_status() -> list[dict]:
    results = []
    for key, agent in SUPPORTED_AGENTS.items():
        if agent.get("format") == "claude-plugin":
            configured = _check_claude_code_plugin()
            results.append(
                {
                    "key": key,
                    "name": agent["name"],
                    "config_path": str(CLAUDE_PLUGIN_DIR),
                    "configured": configured,
                    "config_exists": CLAUDE_PLUGIN_DIR.exists(),
                }
            )
        else:
            config_path: Path = agent["config_path_fn"]()
            config = _read_json(config_path)
            is_configured = "context8" in config.get(agent["config_key"], {})
            results.append(
                {
                    "key": key,
                    "name": agent["name"],
                    "config_path": str(config_path),
                    "configured": is_configured,
                    "config_exists": config_path.exists(),
                }
            )
    return results
