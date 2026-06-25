from __future__ import annotations

import os

from .server_common import create_http_middleware, create_mcp


mcp = create_mcp()


def main() -> None:
    host = os.getenv("FORMAT_EXPORT_HOST", "0.0.0.0")
    port = int(os.getenv("FORMAT_EXPORT_PORT", "8000"))
    mcp.run(transport="http", host=host, port=port, path="/mcp/", middleware=create_http_middleware())


if __name__ == "__main__":
    main()
