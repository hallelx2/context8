"""Docker management for Context8 — start/stop/check the Actian VectorAI DB container.

Generates docker-compose.yml on demand into ~/.context8/ so it works
whether installed via pip, uv, or from source. Never requires the user
to have a compose file in their project.
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
version: "3.8"
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


def _docker_compose_cmd() -> list[str]:
    """Return the docker compose command (v2 first, v1 fallback)."""
    try:
        subprocess.run(
            ["docker", "compose", "version"],
            capture_output=True,
            check=True,
        )
        return ["docker", "compose"]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ["docker-compose"]


def run_compose(args: list[str]) -> subprocess.CompletedProcess:
    """Run a docker compose command against the Context8 compose file."""
    _ensure_compose_file()
    cmd = _docker_compose_cmd() + args
    return subprocess.run(
        cmd,
        cwd=str(_compose_dir()),
        capture_output=True,
        text=True,
    )


def is_container_running() -> bool:
    """Check if the context8_db container is running."""
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", f"name={CONTAINER_NAME}", "--format", "{{{{.Status}}}}"],
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

    logger.info("Starting Actian VectorAI DB container...")
    result = run_compose(["up", "-d"])

    if result.returncode != 0:
        return False, f"docker compose up failed: {result.stderr.strip()}"

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
