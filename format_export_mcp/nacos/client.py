from __future__ import annotations

import inspect
import json
import logging
import socket
import threading
from typing import Any, Callable

import yaml
from v2.nacos import (
    ClientConfigBuilder,
    ConfigParam,
    DeregisterInstanceParam,
    NacosConfigService,
    NacosNamingService,
    RegisterInstanceParam,
)

from .config import NacosConfig

logger = logging.getLogger(__name__)


class NacosClient:
    """Async adapter for the Nacos 3.x Python gRPC SDK."""

    def __init__(self, config: NacosConfig):
        self.config = config
        self._config_service: NacosConfigService | None = None
        self._naming_service: NacosNamingService | None = None
        self._config_cache: dict[str, Any] = {}
        self._cache_lock = threading.RLock()
        self._config_listeners: list[Callable[[dict[str, Any]], Any]] = []
        self._registered_ip: str | None = None

    async def initialize(self) -> None:
        if not self.config.enabled:
            logger.info("Nacos integration disabled")
            return

        sdk_config = self._build_client_config()
        try:
            if self.config.enable_config_center or self.config.enable_hot_reload:
                self._config_service = (
                    await NacosConfigService.create_config_service(sdk_config)
                )
                await self._pull_config()
                if self.config.enable_hot_reload:
                    await self._add_config_listener()

            if self.config.enable_service_discovery:
                self._naming_service = (
                    await NacosNamingService.create_naming_service(sdk_config)
                )
                await self._register_service()
        except Exception:
            logger.exception("Failed to initialize Nacos client")
            await self.shutdown()
            raise

        logger.info(
            "Nacos client initialized: %s, namespace=%s",
            self.config.server_addresses,
            self.config.namespace,
        )

    def _build_client_config(self):
        builder = (
            ClientConfigBuilder()
            .server_address(self.config.server_addresses)
            .namespace_id(self.config.namespace)
            .heart_beat_interval(self.config.heartbeat_interval * 1000)
            .log_level(logging.INFO)
        )
        if self.config.username:
            builder.username(self.config.username)
        if self.config.password:
            builder.password(self.config.password)
        return builder.build()

    async def _pull_config(self) -> None:
        if self._config_service is None:
            return

        content = await self._config_service.get_config(
            ConfigParam(data_id=self.config.data_id, group=self.config.group)
        )
        if not content:
            logger.warning(
                "No config found: data_id=%s, group=%s",
                self.config.data_id,
                self.config.group,
            )
            return

        parsed = self._parse_config(content)
        with self._cache_lock:
            self._config_cache = parsed
        logger.info(
            "Pulled config from Nacos: %s, keys=%s",
            self.config.data_id,
            list(parsed.keys()),
        )

    def _parse_config(self, content: str) -> dict[str, Any]:
        try:
            if self.config.data_id.endswith(".json"):
                parsed = json.loads(content)
            else:
                parsed = yaml.safe_load(content)
        except (json.JSONDecodeError, yaml.YAMLError):
            logger.exception("Failed to parse Nacos configuration")
            return {}

        if not isinstance(parsed, dict):
            logger.warning("Nacos configuration root must be a mapping")
            return {}
        return parsed

    async def _add_config_listener(self) -> None:
        if self._config_service is None:
            return

        async def callback(
            tenant: str,
            data_id: str,
            group: str,
            content: str,
        ) -> None:
            del tenant, data_id, group
            new_config = self._parse_config(content)
            with self._cache_lock:
                self._config_cache = new_config
                listeners = list(self._config_listeners)

            logger.info("Nacos config changed, keys=%s", list(new_config.keys()))
            for listener in listeners:
                try:
                    result = listener(new_config)
                    if inspect.isawaitable(result):
                        await result
                except Exception:
                    logger.exception("Nacos config listener failed")

        await self._config_service.add_listener(
            data_id=self.config.data_id,
            group=self.config.group,
            listener=callback,
        )

    def add_config_listener(
        self,
        listener: Callable[[dict[str, Any]], Any],
    ) -> None:
        with self._cache_lock:
            self._config_listeners.append(listener)

    async def _register_service(self) -> None:
        if self._naming_service is None:
            return

        ip = self.config.ip or self._get_local_ip()
        metadata = {
            "version": "0.1.0",
            "protocol": "http",
            **{key: str(value) for key, value in self.config.metadata.items()},
        }
        await self._naming_service.register_instance(
            request=RegisterInstanceParam(
                service_name=self.config.service_name,
                group_name=self.config.group,
                ip=ip,
                port=self.config.port,
                cluster_name=self.config.cluster_name,
                weight=1.0,
                metadata=metadata,
                enabled=True,
                healthy=True,
                ephemeral=True,
            )
        )
        self._registered_ip = ip
        logger.info(
            "Service registered: %s, %s:%s, cluster=%s",
            self.config.service_name,
            ip,
            self.config.port,
            self.config.cluster_name,
        )

    @staticmethod
    def _get_local_ip() -> str:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.connect(("8.8.8.8", 80))
            return str(sock.getsockname()[0])
        except OSError:
            return "127.0.0.1"
        finally:
            sock.close()

    async def _deregister_service(self) -> None:
        if self._naming_service is None or self._registered_ip is None:
            return

        await self._naming_service.deregister_instance(
            request=DeregisterInstanceParam(
                service_name=self.config.service_name,
                group_name=self.config.group,
                ip=self._registered_ip,
                port=self.config.port,
                cluster_name=self.config.cluster_name,
                ephemeral=True,
            )
        )
        self._registered_ip = None

    def get_config(self, key: str, default: Any = None) -> Any:
        with self._cache_lock:
            if key in self._config_cache:
                return self._config_cache[key]

            value: Any = self._config_cache
            for part in key.split("."):
                if not isinstance(value, dict) or part not in value:
                    return default
                value = value[part]
            return value

    def get_all_config(self) -> dict[str, Any]:
        with self._cache_lock:
            return dict(self._config_cache)

    async def shutdown(self) -> None:
        if self._naming_service is not None:
            try:
                await self._deregister_service()
            except Exception:
                logger.exception("Failed to deregister Nacos service")
            finally:
                try:
                    await self._naming_service.shutdown()
                except Exception:
                    logger.exception("Failed to shut down Nacos naming client")
                self._naming_service = None

        if self._config_service is not None:
            try:
                await self._config_service.shutdown()
            except Exception:
                logger.exception("Failed to shut down Nacos config client")
            self._config_service = None
