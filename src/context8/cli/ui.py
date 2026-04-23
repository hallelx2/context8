from __future__ import annotations

from rich.console import Console

from ..config import DB_URL

console = Console()


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
        console.print(f"[red]X Cannot connect to database:[/] {info}")
        console.print("  Run [cyan]context8 start[/] first\n")
        raise SystemExit(1)
    return info
