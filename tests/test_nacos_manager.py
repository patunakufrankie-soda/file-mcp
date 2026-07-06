from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, Mock, patch

from format_export_mcp.nacos.config import NacosConfig
from format_export_mcp.nacos.manager import NacosManager


class NacosManagerTests(unittest.TestCase):
    def tearDown(self) -> None:
        NacosManager.shutdown()

    def test_disabled_initialization_creates_no_runtime(self) -> None:
        NacosManager.initialize(NacosConfig(enabled=False))

        self.assertIsNone(NacosManager.get_client())
        self.assertIsNone(NacosManager._loop)
        self.assertIsNone(NacosManager._thread)

    def test_runs_async_client_on_background_loop_and_shuts_down(self) -> None:
        client = Mock()
        client.initialize = AsyncMock()
        client.shutdown = AsyncMock()
        client.get_config.return_value = "https://files.example.com"

        with patch(
            "format_export_mcp.nacos.manager.NacosClient",
            return_value=client,
        ):
            NacosManager.initialize(NacosConfig(enabled=True))
            thread = NacosManager._thread

            self.assertIsNotNone(thread)
            self.assertTrue(thread.is_alive())
            client.initialize.assert_awaited_once()
            self.assertEqual(
                NacosManager.get_config("file_server.base_url"),
                "https://files.example.com",
            )

            NacosManager.initialize(NacosConfig(enabled=True))
            client.initialize.assert_awaited_once()

            NacosManager.shutdown()

        client.shutdown.assert_awaited_once()
        self.assertFalse(thread.is_alive())
        self.assertIsNone(NacosManager.get_client())
        self.assertIsNone(NacosManager._loop)
        self.assertIsNone(NacosManager._thread)

    def test_failed_initialization_cleans_up_runtime(self) -> None:
        client = Mock()
        client.initialize = AsyncMock(side_effect=RuntimeError("init failed"))
        client.shutdown = AsyncMock()

        with patch(
            "format_export_mcp.nacos.manager.NacosClient",
            return_value=client,
        ):
            with self.assertRaisesRegex(RuntimeError, "init failed"):
                NacosManager.initialize(NacosConfig(enabled=True))

        client.shutdown.assert_awaited_once()
        self.assertIsNone(NacosManager.get_client())
        self.assertIsNone(NacosManager._loop)
        self.assertIsNone(NacosManager._thread)


if __name__ == "__main__":
    unittest.main()
