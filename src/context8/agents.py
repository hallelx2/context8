from __future__ import annotations

import json
from pathlib import Path

from .config import DB_HOST, DB_PORT, SUPPORTED_AGENTS, get_server_command


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


def add_to_agent(agent_key: str) -> tuple[bool, str]:
    if agent_key not in SUPPORTED_AGENTS:
        supported = ", ".join(sorted(SUPPORTED_AGENTS.keys()))
        return False, f"Unknown agent '{agent_key}'. Supported: {supported}"

    agent = SUPPORTED_AGENTS[agent_key]
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
