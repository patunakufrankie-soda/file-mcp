from __future__ import annotations

import os
import logging
import atexit

from .server_common import create_http_middleware, create_mcp
from .nacos.manager import NacosManager
from .nacos.config import NacosConfig

logger = logging.getLogger(__name__)

mcp = create_mcp()


def main() -> None:
    host = os.getenv("FORMAT_EXPORT_HOST", "0.0.0.0")
    port = int(os.getenv("FORMAT_EXPORT_PORT", "8000"))

    # 初始化 Nacos
    try:
        nacos_config = NacosConfig.from_env()
        nacos_config.ip = None if host == "0.0.0.0" else host
        nacos_config.port = port

        NacosManager.initialize(nacos_config)

        if nacos_config.enabled:
            logger.info(
                f"Nacos integration enabled: config={nacos_config.enable_config_center}, discovery={nacos_config.enable_service_discovery}"
            )

        # 注册关闭钩子
        atexit.register(NacosManager.shutdown)

    except Exception as e:
        logger.warning(f"Failed to initialize Nacos (non-fatal): {e}")

    mcp.run(
        transport="http",
        host=host,
        port=port,
        path="/mcp/",
        middleware=create_http_middleware(),
    )


if __name__ == "__main__":
    main()
