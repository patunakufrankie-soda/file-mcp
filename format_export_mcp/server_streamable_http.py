from __future__ import annotations

import os

from .server_common import create_mcp


mcp = create_mcp()


def main() -> None:
    host = os.getenv("FORMAT_EXPORT_HOST", "127.0.0.1")
    port = int(os.getenv("FORMAT_EXPORT_PORT", "8000"))
    mcp.run(transport="http", host=host, port=port, path="/mcp/")


if __name__ == "__main__":
    main()
