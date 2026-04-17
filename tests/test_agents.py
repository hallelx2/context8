"""Unit tests for agent config management."""

from __future__ import annotations

import json
from unittest.mock import patch

from context8.agents import _read_json, _write_json, add_to_agent, remove_from_agent


class TestReadWriteJson:
    def test_read_missing_file(self, tmp_path):
        assert _read_json(tmp_path / "nope.json") == {}

    def test_read_empty_file(self, tmp_path):
        p = tmp_path / "empty.json"
        p.write_text("")
        assert _read_json(p) == {}

    def test_read_invalid_json(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("{broken")
        assert _read_json(p) == {}

    def test_roundtrip(self, tmp_path):
        p = tmp_path / "test.json"
        data = {"hello": "world", "nested": {"a": 1}}
        _write_json(p, data)
        assert _read_json(p) == data

    def test_write_creates_parents(self, tmp_path):
        p = tmp_path / "a" / "b" / "c.json"
        _write_json(p, {"x": 1})
        assert p.exists()
        assert _read_json(p) == {"x": 1}


class TestAddToAgent:
    def test_add_to_claude(self, tmp_path):
        config_path = tmp_path / "settings.json"

        with patch(
            "context8.agents.SUPPORTED_AGENTS",
            {
                "claude": {
                    "name": "Claude Code",
                    "config_path_fn": lambda: config_path,
                    "config_key": "mcpServers",
                    "format": "standard",
                }
            },
        ):
            ok, msg = add_to_agent("claude")
            assert ok
            assert "Added" in msg

            # Verify JSON written
            data = json.loads(config_path.read_text())
            assert "context8" in data["mcpServers"]
            entry = data["mcpServers"]["context8"]
            assert entry["command"] == "python"
            assert entry["args"] == ["-m", "context8.mcp.server"]

    def test_idempotent(self, tmp_path):
        config_path = tmp_path / "settings.json"

        with patch(
            "context8.agents.SUPPORTED_AGENTS",
            {
                "claude": {
                    "name": "Claude Code",
                    "config_path_fn": lambda: config_path,
                    "config_key": "mcpServers",
                    "format": "standard",
                }
            },
        ):
            add_to_agent("claude")
            ok, msg = add_to_agent("claude")
            assert ok
            assert "already configured" in msg

    def test_preserves_existing_config(self, tmp_path):
        config_path = tmp_path / "settings.json"
        config_path.write_text(json.dumps({"mcpServers": {"other": {"command": "other-tool"}}}))

        with patch(
            "context8.agents.SUPPORTED_AGENTS",
            {
                "claude": {
                    "name": "Claude Code",
                    "config_path_fn": lambda: config_path,
                    "config_key": "mcpServers",
                    "format": "standard",
                }
            },
        ):
            add_to_agent("claude")
            data = json.loads(config_path.read_text())
            assert "other" in data["mcpServers"]
            assert "context8" in data["mcpServers"]

    def test_unknown_agent(self):
        ok, msg = add_to_agent("nonexistent")
        assert not ok
        assert "Unknown" in msg


class TestRemoveFromAgent:
    def test_remove(self, tmp_path):
        config_path = tmp_path / "settings.json"
        config_path.write_text(json.dumps({"mcpServers": {"context8": {"command": "python"}}}))

        with patch(
            "context8.agents.SUPPORTED_AGENTS",
            {
                "claude": {
                    "name": "Claude Code",
                    "config_path_fn": lambda: config_path,
                    "config_key": "mcpServers",
                    "format": "standard",
                }
            },
        ):
            ok, msg = remove_from_agent("claude")
            assert ok
            assert "Removed" in msg

            data = json.loads(config_path.read_text())
            assert "context8" not in data.get("mcpServers", {})

    def test_remove_when_not_configured(self, tmp_path):
        config_path = tmp_path / "settings.json"

        with patch(
            "context8.agents.SUPPORTED_AGENTS",
            {
                "claude": {
                    "name": "Claude Code",
                    "config_path_fn": lambda: config_path,
                    "config_key": "mcpServers",
                    "format": "standard",
                }
            },
        ):
            ok, msg = remove_from_agent("claude")
            assert ok
            assert "not configured" in msg
