from __future__ import annotations

import click

from .. import __version__
from .commands import (
    add,
    bench,
    demo,
    doctor,
    import_github,
    init,
    mine,
    remove,
    search_cmd,
    serve,
    start,
    stats,
    stop,
)


@click.group()
@click.version_option(__version__, prog_name="context8")
def main():
    """Context8 — Collective problem-solving memory for coding agents."""


main.add_command(start)
main.add_command(stop)
main.add_command(init)
main.add_command(add)
main.add_command(remove)
main.add_command(stats)
main.add_command(doctor)
main.add_command(search_cmd)
main.add_command(bench)
main.add_command(demo)
main.add_command(import_github)
main.add_command(mine)
main.add_command(serve)


if __name__ == "__main__":
    main()
