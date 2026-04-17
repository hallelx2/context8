from __future__ import annotations

import subprocess
from pathlib import Path

from rich.console import Console

from ..config import DB_URL, project_root

console = Console()


def docker_compose_cmd() -> list[str]:
    try:
        subprocess.run(
            ["docker", "compose", "version"],
            capture_output=True,
            check=True,
        )
        return ["docker", "compose"]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ["docker-compose"]


def run_docker(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    cmd = docker_compose_cmd() + args
    root = cwd or project_root()
    return subprocess.run(cmd, cwd=root, capture_output=True, text=True)


def check_actian_sdk() -> tuple[bool, str]:
    try:
        import actian_vectorai  # noqa: F401

        return True, "installed"
    except ImportError:
        return False, (
            "not installed — run:\n"
            '    pip install "actian-vectorai @ '
            "https://github.com/hackmamba-io/actian-vectorAI-db-beta/raw/main/"
            'actian_vectorai-0.1.0b2-py3-none-any.whl"'
        )


def check_db_connection() -> tuple[bool, str]:
    try:
        from actian_vectorai import VectorAIClient

        with VectorAIClient(DB_URL, timeout=5.0) as client:
            info = client.health_check()
            return True, f"{info.get('title', 'VectorAI DB')} v{info.get('version', '?')}"
    except ImportError:
        return False, "actian-vectorai SDK not installed"
    except Exception as e:
        return False, str(e)


def require_db() -> str:
    ok, info = check_db_connection()
    if not ok:
        console.print(f"[red]✗ Cannot connect to database:[/] {info}")
        console.print("  Run [cyan]context8 start[/] first\n")
        raise SystemExit(1)
    return info
