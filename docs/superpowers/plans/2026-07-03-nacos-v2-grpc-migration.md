# Nacos 3.x Python gRPC SDK Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the project from the removed synchronous Nacos API to the `nacos-sdk-python` 3.x asynchronous gRPC API without changing synchronous application-facing interfaces.

**Architecture:** `NacosClient` becomes an async adapter around `NacosConfigService` and `NacosNamingService`. `NacosManager` owns a daemon-thread asyncio loop and bridges synchronous startup/shutdown to that adapter with `run_coroutine_threadsafe`.

**Tech Stack:** Python 3.12+, asyncio, threading, nacos-sdk-python 3.2.x, pytest/unittest mocks.

---

### Task 1: Test and implement the asynchronous SDK adapter

**Files:**
- Create: `tests/test_nacos_v2_client.py`
- Modify: `format_export_mcp/nacos/client.py`

- [ ] Add async tests that patch `NacosConfigService.create_config_service` and
  `NacosNamingService.create_naming_service` with `AsyncMock`.
- [ ] Assert builder configuration, `ConfigParam`, initial cache parsing,
  listener registration, `RegisterInstanceParam`, listener notification,
  deregistration, and both service shutdown calls.
- [ ] Run `pytest -q tests/test_nacos_v2_client.py` and verify failures reference
  the legacy `import nacos` implementation.
- [ ] Replace the legacy client with async `v2.nacos` services, a cache lock,
  async initialization, listener callback, registration, and idempotent async
  shutdown.
- [ ] Rerun the client tests and verify they pass.

### Task 2: Test and implement the synchronous manager bridge

**Files:**
- Create: `tests/test_nacos_manager.py`
- Modify: `format_export_mcp/nacos/manager.py`

- [ ] Add tests for disabled initialization, successful initialization,
  synchronous cache access, duplicate initialization, idempotent shutdown, and
  failed initialization cleanup.
- [ ] Run `pytest -q tests/test_nacos_manager.py` and verify the async client
  cannot be called correctly by the current manager.
- [ ] Add a dedicated event loop and daemon thread, bounded future waits,
  centralized state cleanup, and loop/thread teardown.
- [ ] Rerun manager tests and verify no thread remains alive after shutdown or
  initialization failure.

### Task 3: Align dependency constraints and public startup behavior

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Test: `tests/test_nacos_v2_client.py`
- Test: `tests/test_nacos_manager.py`
- Test: `tests/test_input_loader_edge_cases.py`
- Test: `tests/test_export_document_formats.py`

- [ ] Change the dependency constraint to
  `nacos-sdk-python>=3.2,<4` and update the lockfile requirement while retaining
  the resolved 3.x package.
- [ ] Verify `import format_export_mcp.nacos` and `import v2.nacos`.
- [ ] Run Nacos, input-loader, and server startup tests.
- [ ] Run the full test suite.
- [ ] Run `python3 -m py_compile` for changed Python files and
  `git diff --check`.
- [ ] Confirm no test opens a real Nacos connection and report any upstream
  warnings separately.
