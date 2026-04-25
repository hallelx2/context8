"""Container runtime management for Context8 — start/stop/check the Actian
VectorAI DB container.

Generates a compose file on demand into ~/.context8/ so it works whether
installed via pip, uv, or from source. Supports both Docker and Podman —
the runtime is detected automatically.
"""

from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path

from .config import DB_URL, _home

logger = logging.getLogger("context8.docker")

CONTEXT8_DIR = _home() / ".context8"

COMPOSE_TEMPLATE = """\
services:
  vectoraidb:
    image: docker.io/williamimoh/actian-vectorai-db:latest
    container_name: context8_db
    ports:
      - "50051:50051"
    volumes:
      - {data_dir}:/data
    restart: unless-stopped
    stop_grace_period: 2m
"""

CONTAINER_NAME = "context8_db"

_runtime_cache: str | None = None
_compose_cache: list[str] | None = None


def _compose_dir() -> Path:
    """Return ~/.context8/ — where we keep the generated compose file."""
    CONTEXT8_DIR.mkdir(parents=True, exist_ok=True)
    return CONTEXT8_DIR


def _ensure_compose_file() -> Path:
    """Generate docker-compose.yml in ~/.context8/ if not present."""
    compose_path = _compose_dir() / "docker-compose.yml"
    data_dir = _compose_dir() / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    if not compose_path.exists():
        content = COMPOSE_TEMPLATE.format(data_dir=str(data_dir).replace("\\", "/"))
        compose_path.write_text(content, encoding="utf-8")
        logger.info(f"Generated {compose_path}")

    return compose_path


def _probe(cmd: list[str]) -> bool:
    try:
        subprocess.run(cmd, capture_output=True, check=True, timeout=5)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False


def detect_runtime() -> str | None:
    """Return 'docker' or 'podman' — the first runtime whose daemon is reachable.

    Prefers a *working* runtime over a merely installed one: if docker is
    installed but its daemon is down, falls through to podman. Returns None
    if neither is usable.
    """
    global _runtime_cache
    if _runtime_cache is not None:
        return _runtime_cache or None

    # First pass: pick a runtime whose daemon is actually reachable.
    for candidate in ("docker", "podman"):
        if _probe([candidate, "info"]):
            _runtime_cache = candidate
            return candidate

    # Second pass: any installed runtime, even if the daemon is down — so
    # callers can still surface a useful error message.
    for candidate in ("docker", "podman"):
        if _probe([candidate, "--version"]):
            _runtime_cache = candidate
            return candidate

    _runtime_cache = ""
    return None


def _compose_cmd() -> list[str] | None:
    """Return the compose command for the detected runtime, or None.

    Tries (in order): `docker compose`, `docker-compose`, `podman compose`,
    `podman-compose`.
    """
    global _compose_cache
    if _compose_cache is not None:
        return _compose_cache or None

    candidates: list[list[str]] = []
    runtime = detect_runtime()
    if runtime == "docker":
        candidates = [["docker", "compose"], ["docker-compose"]]
    elif runtime == "podman":
        candidates = [["podman", "compose"], ["podman-compose"]]
    else:
        # Try everything anyway in case the runtime probe missed something
        candidates = [
            ["docker", "compose"],
            ["podman", "compose"],
            ["podman-compose"],
            ["docker-compose"],
        ]

    for cmd in candidates:
        if _probe(cmd + ["version"]):
            _compose_cache = cmd
            return cmd

    _compose_cache = []
    return None


def run_compose(args: list[str]) -> subprocess.CompletedProcess:
    """Run a compose command against the Context8 compose file."""
    _ensure_compose_file()
    cmd = _compose_cmd()
    if cmd is None:
        return subprocess.CompletedProcess(
            args=args,
            returncode=1,
            stdout="",
            stderr=(
                "no compose tool found — install one of: "
                "`docker compose`, `podman compose`, `podman-compose`, `docker-compose`"
            ),
        )
    return subprocess.run(
        cmd + args,
        cwd=str(_compose_dir()),
        capture_output=True,
        text=True,
    )


def is_container_running() -> bool:
    """Check if the context8_db container is running under docker or podman."""
    runtime = detect_runtime()
    if runtime is None:
        return False
    try:
        result = subprocess.run(
            [runtime, "ps", "--filter", f"name={CONTAINER_NAME}", "--format", "{{.Status}}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return bool(result.stdout.strip()) and "Up" in result.stdout
    except Exception:
        return False


def ensure_running(timeout_secs: int = 30) -> tuple[bool, str]:
    """Start the container if not running, wait for it to be healthy.

    Returns (success, message).
    """
    if is_container_running():
        return True, "already running"

    runtime = detect_runtime() or "container runtime"
    logger.info(f"Starting Actian VectorAI DB container via {runtime}...")
    result = run_compose(["up", "-d"])

    if result.returncode != 0:
        return False, f"compose up failed: {result.stderr.strip()}"

    # Wait for the DB to accept connections
    for _ in range(timeout_secs):
        try:
            from actian_vectorai import VectorAIClient

            with VectorAIClient(DB_URL, timeout=3.0) as client:
                info = client.health_check()
                return True, f"started — {info.get('title', 'DB')} v{info.get('version', '?')}"
        except Exception:
            time.sleep(1)

    return False, f"container started but DB not ready after {timeout_secs}s"


def stop_container() -> tuple[bool, str]:
    """Stop the container."""
    result = run_compose(["down"])
    if result.returncode == 0:
        return True, "stopped"
    return False, result.stderr.strip()
