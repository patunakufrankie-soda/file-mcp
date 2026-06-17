# Format Export MCP 服务器部署要点

本文档面向后端部署同事，只保留部署时容易影响可用性的关键点。

## 1. 镜像加载与启动

```bash
docker load -i format-export-mcp-latest.tar

docker rm -f format-export-mcp 2>/dev/null || true

docker run -d \
  --name format-export-mcp \
  --restart unless-stopped \
  -p 8000:8000 \
  -e FORMAT_EXPORT_HOST=0.0.0.0 \
  -e FORMAT_EXPORT_PORT=8000 \
  -e FORMAT_EXPORT_STORAGE_DIR=/app/format_export_mcp/storage/exports \
  -e FORMAT_EXPORT_PUBLIC_BASE_URL=/downloads \
  -e FORMAT_EXPORT_FILE_TTL_SECONDS=604800 \
  -e FORMAT_EXPORT_RATE_LIMIT_PER_MINUTE=20 \
  -v /data/format-export/exports:/app/format_export_mcp/storage/exports \
  format-export-mcp:latest
```

## 2. 最重要：挂载目录必须可写

容器默认非 root 运行，导出文件目录必须挂载并保证容器内用户可写。

推荐宿主机目录：

```bash
/data/format-export/exports
```

测试环境可以直接：

```bash
mkdir -p /data/format-export/exports
chmod 777 /data/format-export/exports
```

更规范的做法是查容器内 UID/GID 后 `chown`：

```bash
docker run --rm format-export-mcp:latest id
chown -R <uid>:<gid> /data/format-export/exports
chmod 755 /data/format-export/exports
```

如果目录不可写，`/health` 可能仍然正常，但 `/ready` 会失败，导出接口也会写盘失败。

## 3. 探活

`/health` 只表示进程存活：

```bash
curl http://127.0.0.1:8000/health
```

`/ready` 会检查导出目录是否存在且可写，部署和接流量前应以它为准：

```bash
curl http://127.0.0.1:8000/ready
```

## 4. 下载前缀

如果服务直接通过 `http://server:8000` 访问，可以保持：

```bash
FORMAT_EXPORT_PUBLIC_BASE_URL=/downloads
```

如果前面有 Nginx 或网关域名，建议设置为完整下载地址：

```bash
FORMAT_EXPORT_PUBLIC_BASE_URL=https://format-export.example.com/downloads
```

否则接口返回的 `file_url` 可能不是前端可直接访问的地址。

## 5. 文件保留与限流

导出文件会按 TTL 清理：

```bash
FORMAT_EXPORT_FILE_TTL_SECONDS=604800
```

示例值是 7 天。需要 30 天可改为：

```bash
FORMAT_EXPORT_FILE_TTL_SECONDS=2592000
```

HTTP 辅助导出接口有单 IP 限流：

```bash
FORMAT_EXPORT_RATE_LIMIT_PER_MINUTE=20
```

触发后返回 `429`。

## 6. 验证导出

```bash
curl -X POST http://127.0.0.1:8000/api/export_document \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: deploy-test-001" \
  -d '{"title":"部署测试","content":"hello","format":"txt"}'
```

返回里的 `file_url` 应可下载：

```bash
curl "http://127.0.0.1:8000/downloads/<file_name>"
```

## 7. 日志

```bash
docker logs -f format-export-mcp
```

导出接口会输出 JSON 日志，重点字段：

- `event`
- `request_id`
- `client_host`
- `status_code`
- `duration_ms`
- `file_name`
- `format`
- `error_code`

如果调用方传 `X-Request-ID`，响应头和日志都会带同一个值。

## 8. 部署注意点

- 不建议裸跑 `docker run -d -p 8000:8000 format-export-mcp:latest`，因为没有挂载目录和自动重启。
- 生产环境建议放在 Nginx 或平台网关后面，不建议容器端口直接暴露公网。
- 当前服务没有 Token 鉴权，至少应限制网络访问范围，并保留限流。
- 升级镜像前确认宿主机挂载目录不变，避免历史导出文件看起来“丢失”。
