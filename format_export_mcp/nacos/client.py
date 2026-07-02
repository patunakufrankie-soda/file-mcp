from __future__ import annotations

import logging
import json
import yaml
import socket
from typing import Callable, Any

import nacos

from .config import NacosConfig

logger = logging.getLogger(__name__)


class NacosClient:
    """Nacos 客户端：配置中心 + 服务注册 + 热更新"""

    def __init__(self, config: NacosConfig):
        self.config = config
        self._client: nacos.NacosClient | None = None
        self._config_cache: dict[str, Any] = {}
        self._config_listeners: list[Callable[[dict[str, Any]], None]] = []

    def initialize(self) -> None:
        """初始化 Nacos 客户端"""
        if not self.config.enabled:
            logger.info("Nacos integration disabled")
            return

        try:
            self._client = nacos.NacosClient(
                server_addresses=self.config.server_addresses,
                namespace=self.config.namespace,
                username=self.config.username,
                password=self.config.password,
            )
            logger.info(
                f"Nacos client initialized: {self.config.server_addresses}, namespace={self.config.namespace}"
            )

            # 拉取配置
            if self.config.enable_config_center:
                self._pull_config()

            # 注册服务
            if self.config.enable_service_discovery:
                self._register_service()

            # 监听配置变更
            if self.config.enable_hot_reload:
                self._add_config_listener()

        except Exception as e:
            logger.error(f"Failed to initialize Nacos client: {e}")
            raise

    def _pull_config(self) -> None:
        """从 Nacos 配置中心拉取配置"""
        if not self._client:
            return

        try:
            content = self._client.get_config(
                data_id=self.config.data_id,
                group=self.config.group,
            )

            if content:
                self._config_cache = self._parse_config(content)
                logger.info(
                    f"Pulled config from Nacos: {self.config.data_id}, keys={list(self._config_cache.keys())}"
                )
            else:
                logger.warning(
                    f"No config found: data_id={self.config.data_id}, group={self.config.group}"
                )

        except Exception as e:
            logger.error(f"Failed to pull config from Nacos: {e}")

    def _parse_config(self, content: str) -> dict[str, Any]:
        """解析配置内容（支持 YAML/JSON）"""
        try:
            # 尝试 YAML
            if self.config.data_id.endswith((".yaml", ".yml")):
                return yaml.safe_load(content) or {}
            # 尝试 JSON
            elif self.config.data_id.endswith(".json"):
                return json.loads(content)
            # 默认 YAML
            else:
                return yaml.safe_load(content) or {}
        except Exception as e:
            logger.error(f"Failed to parse config content: {e}")
            return {}

    def _add_config_listener(self) -> None:
        """监听配置变更"""
        if not self._client:
            return

        def callback(content: str) -> None:
            try:
                new_config = self._parse_config(content)
                logger.info(f"Config changed, new keys={list(new_config.keys())}")
                self._config_cache = new_config

                # 通知所有监听器
                for listener in self._config_listeners:
                    try:
                        listener(new_config)
                    except Exception as e:
                        logger.error(f"Config listener error: {e}")

            except Exception as e:
                logger.error(f"Failed to handle config change: {e}")

        try:
            self._client.add_config_watcher(
                data_id=self.config.data_id,
                group=self.config.group,
                cb=callback,
            )
            logger.info(
                f"Config listener added: data_id={self.config.data_id}, group={self.config.group}"
            )
        except Exception as e:
            logger.error(f"Failed to add config listener: {e}")

    def add_config_listener(self, listener: Callable[[dict[str, Any]], None]) -> None:
        """注册配置变更监听器"""
        self._config_listeners.append(listener)

    def _register_service(self) -> None:
        """注册服务实例到 Nacos"""
        if not self._client:
            return

        try:
            ip = self.config.ip or self._get_local_ip()
            port = self.config.port

            metadata = {
                "version": "0.1.0",
                "protocol": "http",
                **self.config.metadata,
            }

            self._client.add_naming_instance(
                service_name=self.config.service_name,
                ip=ip,
                port=port,
                cluster_name=self.config.cluster_name,
                weight=1.0,
                metadata=metadata,
                enable=True,
                healthy=True,
            )

            logger.info(
                f"Service registered: {self.config.service_name}, {ip}:{port}, cluster={self.config.cluster_name}"
            )

        except Exception as e:
            logger.error(f"Failed to register service: {e}")

    def _get_local_ip(self) -> str:
        """获取本机 IP"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def deregister_service(self) -> None:
        """注销服务实例"""
        if not self._client or not self.config.enable_service_discovery:
            return

        try:
            ip = self.config.ip or self._get_local_ip()
            port = self.config.port

            self._client.remove_naming_instance(
                service_name=self.config.service_name,
                ip=ip,
                port=port,
                cluster_name=self.config.cluster_name,
            )

            logger.info(
                f"Service deregistered: {self.config.service_name}, {ip}:{port}"
            )

        except Exception as e:
            logger.error(f"Failed to deregister service: {e}")

    def get_config(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        return self._config_cache.get(key, default)

    def get_all_config(self) -> dict[str, Any]:
        """获取所有配置"""
        return self._config_cache.copy()

    def shutdown(self) -> None:
        """关闭客户端"""
        self.deregister_service()
        if self._client:
            try:
                self._client.stop()
                logger.info("Nacos client stopped")
            except Exception as e:
                logger.error(f"Error stopping Nacos client: {e}")
