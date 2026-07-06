from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, Mock, patch

from format_export_mcp.nacos.client import NacosClient
from format_export_mcp.nacos.config import NacosConfig


class NacosV2ClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_initializes_services_and_handles_config_updates(self) -> None:
        config_service = Mock()
        config_service.get_config = AsyncMock(
            return_value="file_server:\n  base_url: https://files.example.com\n"
        )
        config_service.add_listener = AsyncMock()
        config_service.shutdown = AsyncMock()

        naming_service = Mock()
        naming_service.register_instance = AsyncMock(return_value=True)
        naming_service.deregister_instance = AsyncMock(return_value=True)
        naming_service.shutdown = AsyncMock()

        config = NacosConfig(
            enabled=True,
            enable_config_center=True,
            enable_hot_reload=True,
            enable_service_discovery=True,
            server_addresses="nacos.internal:8848",
            namespace="production",
            username="nacos-user",
            password="nacos-password",
            data_id="format-export-mcp.yaml",
            group="APP_GROUP",
            service_name="format-export-mcp",
            cluster_name="PRIMARY",
            ip="10.0.0.8",
            port=8000,
            heartbeat_interval=9,
        )
        listener = Mock()

        with (
            patch(
                "format_export_mcp.nacos.client."
                "NacosConfigService.create_config_service",
                new=AsyncMock(return_value=config_service),
            ) as create_config_service,
            patch(
                "format_export_mcp.nacos.client."
                "NacosNamingService.create_naming_service",
                new=AsyncMock(return_value=naming_service),
            ) as create_naming_service,
        ):
            client = NacosClient(config)
            client.add_config_listener(listener)
            await client.initialize()

            sdk_config = create_config_service.await_args.args[0]
            self.assertEqual(sdk_config.server_list, ["nacos.internal:8848"])
            self.assertEqual(sdk_config.namespace_id, "production")
            self.assertEqual(sdk_config.username, "nacos-user")
            self.assertEqual(sdk_config.password, "nacos-password")
            self.assertEqual(sdk_config.heart_beat_interval, 9000)
            create_naming_service.assert_awaited_once_with(sdk_config)

            config_param = config_service.get_config.await_args.args[0]
            self.assertEqual(config_param.data_id, "format-export-mcp.yaml")
            self.assertEqual(config_param.group, "APP_GROUP")
            self.assertEqual(
                client.get_config("file_server.base_url"),
                "https://files.example.com",
            )

            register_param = naming_service.register_instance.await_args.kwargs[
                "request"
            ]
            self.assertEqual(register_param.service_name, "format-export-mcp")
            self.assertEqual(register_param.group_name, "APP_GROUP")
            self.assertEqual(register_param.cluster_name, "PRIMARY")
            self.assertEqual(register_param.ip, "10.0.0.8")
            self.assertEqual(register_param.port, 8000)
            self.assertTrue(register_param.ephemeral)

            sdk_listener = config_service.add_listener.await_args.kwargs[
                "listener"
            ]
            await sdk_listener(
                "production",
                "format-export-mcp.yaml",
                "APP_GROUP",
                "file_server:\n  base_url: https://new.example.com\n",
            )
            self.assertEqual(
                client.get_config("file_server.base_url"),
                "https://new.example.com",
            )
            listener.assert_called_once()

            await client.shutdown()

        deregister_param = naming_service.deregister_instance.await_args.kwargs[
            "request"
        ]
        self.assertEqual(deregister_param.service_name, "format-export-mcp")
        config_service.shutdown.assert_awaited_once()
        naming_service.shutdown.assert_awaited_once()

    async def test_disabled_client_does_not_create_sdk_services(self) -> None:
        config = NacosConfig(enabled=False)
        with (
            patch(
                "format_export_mcp.nacos.client."
                "NacosConfigService.create_config_service",
                new=AsyncMock(),
            ) as create_config_service,
            patch(
                "format_export_mcp.nacos.client."
                "NacosNamingService.create_naming_service",
                new=AsyncMock(),
            ) as create_naming_service,
        ):
            client = NacosClient(config)
            await client.initialize()
            await client.shutdown()

        create_config_service.assert_not_awaited()
        create_naming_service.assert_not_awaited()

    async def test_partial_initialization_shuts_down_created_service(self) -> None:
        config_service = Mock()
        config_service.get_config = AsyncMock(return_value="")
        config_service.shutdown = AsyncMock()
        config = NacosConfig(
            enabled=True,
            enable_config_center=True,
            enable_service_discovery=True,
        )

        with (
            patch(
                "format_export_mcp.nacos.client."
                "NacosConfigService.create_config_service",
                new=AsyncMock(return_value=config_service),
            ),
            patch(
                "format_export_mcp.nacos.client."
                "NacosNamingService.create_naming_service",
                new=AsyncMock(side_effect=RuntimeError("naming failed")),
            ),
        ):
            client = NacosClient(config)
            with self.assertRaisesRegex(RuntimeError, "naming failed"):
                await client.initialize()

        config_service.shutdown.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
