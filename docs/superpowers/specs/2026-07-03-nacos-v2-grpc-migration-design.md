# Nacos 3.x Python gRPC SDK Migration

## Goal

Replace the legacy synchronous `import nacos` integration with the current
`nacos-sdk-python` 3.x API exposed through `v2.nacos`, while preserving the
synchronous interfaces used by the FastMCP server and document conversion
code.

## Dependency Contract

The project will require `nacos-sdk-python>=3.2,<4`. This selects the current
3.x SDK family without allowing an unreviewed future major-version migration.
The lock file must resolve a 3.x release that exposes `v2.nacos`.

This migration uses the SDK's gRPC clients. It does not call the removed Nacos
1.x or 2.x HTTP OpenAPI.

## SDK Client

`format_export_mcp.nacos.client.NacosClient` remains the project-facing
adapter, but its implementation becomes asynchronous.

It will:

- build the SDK configuration with `ClientConfigBuilder`;
- map server address, namespace, username, password, and log level;
- create `NacosConfigService` when configuration or hot reload is enabled;
- create `NacosNamingService` when service discovery is enabled;
- fetch configuration through `ConfigParam`;
- register and deregister the service through
  `RegisterInstanceParam` and `DeregisterInstanceParam`;
- subscribe to configuration changes through `add_listener`;
- shut down both SDK service clients.

The adapter keeps a thread-safe in-memory configuration cache. Existing
callers continue to read this cache synchronously through `get_config()`.

The configuration-listener callback uses the SDK's asynchronous
`(tenant, data_id, group, content)` signature. It parses the new content,
atomically replaces the cache, and then notifies project listeners.

## Synchronous Manager Compatibility

`NacosManager` retains synchronous `initialize()`, `get_config()`, and
`shutdown()` methods because the server entry points and input loader are
synchronous.

When Nacos is enabled, the manager will:

1. create a dedicated asyncio event loop;
2. run that loop in a daemon thread;
3. submit the asynchronous client initialization with
   `asyncio.run_coroutine_threadsafe`;
4. wait for initialization with a bounded timeout;
5. retain the loop and thread for gRPC callbacks and reconnect activity.

Shutdown submits the asynchronous client shutdown to the same loop, waits
with a bounded timeout, stops the loop, joins the thread, and clears all
manager state.

When Nacos is disabled, no client, loop, or thread is created.

## Failure Handling

Initialization is atomic from the manager's perspective. If SDK client
creation, configuration loading, listener registration, or service
registration fails, the manager will:

- attempt to shut down any partially created SDK services;
- stop and join the event-loop thread;
- clear all class-level state;
- re-raise the initialization error for the server entry point to log.

The server remains able to start because its existing Nacos initialization
block treats the integration as non-fatal.

Shutdown is idempotent. Repeated calls must not raise or leave a running
thread.

## Service Registration

Registration retains the existing environment contract:

- `NACOS_SERVICE_NAME`;
- `NACOS_SERVICE_IP`, with local-IP fallback;
- `NACOS_SERVICE_PORT`;
- `NACOS_CLUSTER_NAME`;
- metadata containing application version and protocol.

The registration group is the configured Nacos group. Instances remain
ephemeral so the SDK manages heartbeats through gRPC.

## Testing

Tests will not require a live Nacos server. They will mock the 3.x SDK service
factories and assert:

- `ClientConfigBuilder` receives the configured values;
- configuration is fetched and parsed;
- hot-reload callbacks update the cache and notify listeners;
- registration and deregistration parameters are correct;
- both SDK clients are shut down;
- disabled initialization creates no background thread;
- manager initialization and shutdown correctly own the event loop;
- initialization failure cleans up the loop, thread, and client state;
- `import format_export_mcp.nacos` succeeds with the installed 3.x SDK.

The existing input-loader and server tests must remain green because their
synchronous public interfaces do not change.
