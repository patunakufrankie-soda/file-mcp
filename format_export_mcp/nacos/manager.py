from __future__ import annotations

import logging
from typing import Any

from .client import NacosClient
from .config import NacosConfig

logger = logging.getLogger(__name__)


class NacosManager:
    """Nacos 全局管理器"""

    _instance: NacosManager | None = None
    _client: NacosClient | None = None

    def __new__(cls) -> NacosManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def initialize(cls, config: NacosConfig | None = None) -> None:
        """初始化 Nacos 管理器"""
        if cls._client is not None:
            logger.warning("NacosManager already initialized")
            return

        if config is None:
            config = NacosConfig.from_env()

        if not config.enabled:
            logger.info("Nacos disabled, skipping initialization")
            return

        cls._client = NacosClient(config)
        cls._client.initialize()

    @classmethod
    def get_client(cls) -> NacosClient | None:
        """获取 Nacos 客户端"""
        return cls._client

    @classmethod
    def get_config(cls, key: str, default: Any = None) -> Any:
        """获取配置项"""
        if cls._client is None:
            return default
        return cls._client.get_config(key, default)

    @classmethod
    def shutdown(cls) -> None:
        """关闭 Nacos 客户端"""
        if cls._client:
            cls._client.shutdown()
            cls._client = None
