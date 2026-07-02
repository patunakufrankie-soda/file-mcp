from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


@dataclass
class NacosConfig:
    """Nacos 配置"""

    # Nacos 服务器地址
    server_addresses: str = "localhost:8848"

    # 命名空间
    namespace: str = "public"

    # 配置中心
    data_id: str = "format-export-mcp.yaml"
    group: str = "DEFAULT_GROUP"

    # 服务注册
    service_name: str = "format-export-mcp"
    cluster_name: str = "DEFAULT"

    # 认证
    username: str | None = None
    password: str | None = None

    # 服务实例信息
    ip: str | None = None
    port: int = 8000

    # 心跳间隔（秒）
    heartbeat_interval: int = 5

    # 是否启用
    enabled: bool = False
    enable_config_center: bool = False
    enable_service_discovery: bool = False
    enable_hot_reload: bool = False

    # 额外元数据
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> NacosConfig:
        """从环境变量加载 Nacos 配置"""
        return cls(
            server_addresses=os.getenv("NACOS_SERVER_ADDRESSES", "localhost:8848"),
            namespace=os.getenv("NACOS_NAMESPACE", "public"),
            data_id=os.getenv("NACOS_DATA_ID", "format-export-mcp.yaml"),
            group=os.getenv("NACOS_GROUP", "DEFAULT_GROUP"),
            service_name=os.getenv("NACOS_SERVICE_NAME", "format-export-mcp"),
            cluster_name=os.getenv("NACOS_CLUSTER_NAME", "DEFAULT"),
            username=os.getenv("NACOS_USERNAME"),
            password=os.getenv("NACOS_PASSWORD"),
            ip=os.getenv("NACOS_SERVICE_IP"),
            port=int(os.getenv("NACOS_SERVICE_PORT", "8000")),
            heartbeat_interval=int(os.getenv("NACOS_HEARTBEAT_INTERVAL", "5")),
            enabled=os.getenv("NACOS_ENABLED", "false").lower() == "true",
            enable_config_center=os.getenv("NACOS_ENABLE_CONFIG", "false").lower()
            == "true",
            enable_service_discovery=os.getenv(
                "NACOS_ENABLE_DISCOVERY", "false"
            ).lower()
            == "true",
            enable_hot_reload=os.getenv("NACOS_ENABLE_HOT_RELOAD", "false").lower()
            == "true",
        )
