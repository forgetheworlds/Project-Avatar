"""Console entry for the `avatar` setuptools script (Wave 0)."""

from __future__ import annotations

import argparse
import asyncio
import sys
from importlib.metadata import version


def main(argv: list[str] | None = None) -> None:
    """Run the MCP server, or print ``--version`` and exit."""
    parser = argparse.ArgumentParser(prog="avatar")
    parser.add_argument("--version", action="store_true", help="Print package version and exit.")
    ns, _unknown = parser.parse_known_args(argv if argv is not None else sys.argv[1:])
    if ns.version:
        print(version("drone-control-system"))
        return

    from avatar.mcp_server.server import main as srv_main

    asyncio.run(srv_main())
