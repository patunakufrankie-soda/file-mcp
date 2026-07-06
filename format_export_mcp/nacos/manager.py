from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any, Coroutine

from .client import NacosClient
from .config import NacosConfig

logger = logging.getLogger(__name__)

_INITIALIZE_TIMEOUT_SECONDS = 30
_SHUTDOWN_TIMEOUT_SECONDS = 15


class NacosManager:
    """Synchronous lifecycle bridge for the async Nacos gRPC client."""

    _client: NacosClient | None = None
    _loop: asyncio.AbstractEventLoop | None = None
    _thread: threading.Thread | None = None
    _state_lock = threading.RLock()

    @classmethod
    def initialize(cls, config: NacosConfig | None = None) -> None:
        with cls._state_lock:
            if cls._client is not None:
                logger.warning("NacosManager already initialized")
                return

            config = config or NacosConfig.from_env()
            if not config.enabled:
                logger.info("Nacos disabled, skipping initialization")
                return

            loop = asyncio.new_event_loop()
            thread = threading.Thread(
                target=cls._run_event_loop,
                args=(loop,),
                name="nacos-grpc-loop",
                daemon=True,
            )
            client = NacosClient(config)

            cls._loop = loop
            cls._thread = thread
            cls._client = client
            thread.start()

            try:
                cls._submit(
                    client.initialize(),
                    timeout=_INITIALIZE_TIMEOUT_SECONDS,
                )
            except Exception:
                logger.exception("Nacos manager initialization failed")
                try:
                    cls._submit(
                        client.shutdown(),
                        timeout=_SHUTDOWN_TIMEOUT_SECONDS,
                    )
                except Exception:
                    logger.exception(
                        "Failed to clean up Nacos client after initialization error"
                    )
                cls._stop_runtime(loop, thread)
                cls._clear_state()
                raise

    @staticmethod
    def _run_event_loop(loop: asyncio.AbstractEventLoop) -> None:
        asyncio.set_event_loop(loop)
        try:
            loop.run_forever()
        finally:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
            loop.close()

    @classmethod
    def _submit(
        cls,
        coroutine: Coroutine[Any, Any, Any],
        *,
        timeout: float,
    ) -> Any:
        loop = cls._loop
        if loop is None:
            coroutine.close()
            raise RuntimeError("Nacos event loop is not available")

        future = asyncio.run_coroutine_threadsafe(coroutine, loop)
        return future.result(timeout=timeout)

    @staticmethod
    def _stop_runtime(
        loop: asyncio.AbstractEventLoop,
        thread: threading.Thread,
    ) -> None:
        if loop.is_running():
            loop.call_soon_threadsafe(loop.stop)
        if thread is not threading.current_thread():
            thread.join(timeout=_SHUTDOWN_TIMEOUT_SECONDS)
            if thread.is_alive():
                logger.error("Nacos event loop thread did not stop in time")

    @classmethod
    def _clear_state(cls) -> None:
        cls._client = None
        cls._loop = None
        cls._thread = None

    @classmethod
    def get_client(cls) -> NacosClient | None:
        return cls._client

    @classmethod
    def get_config(cls, key: str, default: Any = None) -> Any:
        client = cls._client
        if client is None:
            return default
        return client.get_config(key, default)

    @classmethod
    def shutdown(cls) -> None:
        with cls._state_lock:
            client = cls._client
            loop = cls._loop
            thread = cls._thread

            if client is None or loop is None or thread is None:
                cls._clear_state()
                return

            try:
                cls._submit(
                    client.shutdown(),
                    timeout=_SHUTDOWN_TIMEOUT_SECONDS,
                )
            except Exception:
                logger.exception("Failed to shut down Nacos client")
            finally:
                cls._stop_runtime(loop, thread)
                cls._clear_state()
