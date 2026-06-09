from __future__ import annotations

from .server_common import create_mcp


mcp = create_mcp()


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
