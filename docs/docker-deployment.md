# Format Export MCP 服务器部署要点

本文档面向后端部署同事，按“先判断服务器架构，再构建，再上传，再启动，再验证”的顺序整理。

## 1. 先判断服务器架构

不要先假设一定是 `amd64` 或 `arm64`，先在目标服务器上执行：

```bash
uname -m
```

常见结果：

- `x86_64`：对应 Docker 平台 `linux/amd64`
- `aarch64` 或 `arm64`：对应 Docker 平台 `linux/arm64`

如果公司服务器是普通 Intel/AMD Linux 机器，通常就是 `x86_64`，这时仍然应该构建 `linux/amd64`。

## 2. 本地构建镜像

假设你在本地 Mac 上构建，再上传到公司服务器。

如果服务器是 `x86_64`：

```bash
docker buildx build \
  --platform linux/amd64 \
  -f format_export_mcp/Dockerfile \
  -t format-export-mcp:latest \
  --load .
```

如果服务器是 `aarch64` / `arm64`：

```bash
docker buildx build \
  --platform linux/arm64 \
  -f format_export_mcp/Dockerfile \
  -t format-export-mcp:latest \
  --load .
```

构建完成后导出 tar：

```bash
docker save -o format-export-mcp-latest.tar format-export-mcp:latest
```

可选检查：

```bash
docker image inspect --format '{{.Architecture}}' format-export-mcp:latest
ls -lh format-export-mcp-latest.tar
```

## 3. 上传到服务器

把 tar 传到目标服务器：

```bash
scp format-export-mcp-latest.tar <user>@<server>:/home/<user>/
```

登录服务器：

```bash
ssh <user>@<server>
```

确认文件已经在服务器上：

```bash
ls -lh ~/format-export-mcp-latest.tar
```

## 4. 服务器加载镜像并启动

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
  -e FORMAT_EXPORT_PUBLIC_BASE_URL=http://你的AWS公网IP:8000/downloads \
  -e FILE_SERVER_BASE_URL=https://你的文件服务域名 \
  -e FORMAT_EXPORT_FILE_TTL_SECONDS=604800 \
  -e FORMAT_EXPORT_RATE_LIMIT_PER_MINUTE=20 \
  -e 'FORMAT_EXPORT_ALLOWED_ORIGINS=*' \
  -v /data/format-export/exports:/app/format_export_mcp/storage/exports \
  format-export-mcp:latest
```

镜像加载后可选检查一次服务器上的镜像架构：

```bash
docker image inspect --format '{{.Architecture}}' format-export-mcp:latest
```

如果这里显示的架构和 `uname -m` 对不上，就不要继续启动，回到本地重新按正确平台构建。

## 5. 最重要：挂载目录必须可写

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

如果启动后 `/ready` 返回 `Export storage is not writable`，建议直接这样修：

```bash
APP_UID=$(docker exec format-export-mcp id -u)
APP_GID=$(docker exec format-export-mcp id -g)

sudo chown -R "$APP_UID:$APP_GID" /data/format-export/exports
sudo chmod 755 /data/format-export/exports

docker restart format-export-mcp
```

## 6. 探活

`/health` 只表示进程存活：

```bash
curl http://127.0.0.1:8000/health
```

`/ready` 会检查导出目录是否存在且可写，部署和接流量前应以它为准：

```bash
curl http://127.0.0.1:8000/ready
```

## 7. 下载前缀

如果服务直接通过 `http://server:8000` 访问，可以保持：

```bash
FORMAT_EXPORT_PUBLIC_BASE_URL=/downloads
```

如果前面有 Nginx 或网关域名，建议设置为完整下载地址：

```bash
FORMAT_EXPORT_PUBLIC_BASE_URL=https://format-export.example.com/downloads
```

否则接口返回的 `file_url` 可能不是前端可直接访问的地址。

如果调用方会传相对文件地址，例如：

```text
/api/file/abc123
```

还必须配置文件服务基址：

```bash
FILE_SERVER_BASE_URL=https://platform.example.com
```

服务端会把它拼成：

```text
https://platform.example.com/api/file/abc123
```

如果不配这个变量，`/api/convert_file_document` 在收到相对 `input_uri` 时会直接返回参数错误。

## 8. 文件保留与限流

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

如果前端页面和导出服务不在同一个 Origin，需要允许跨域：

```bash
FORMAT_EXPORT_ALLOWED_ORIGINS=*
```

生产环境更推荐写成逗号分隔的白名单，例如：

```bash
FORMAT_EXPORT_ALLOWED_ORIGINS=https://app.example.com,http://10.89.6.208:3000
```

## 9. 验证导出

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

文件转换接口验证：

```bash
curl -X POST http://127.0.0.1:8000/api/convert_file_document \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: deploy-file-convert-001" \
  -d '{"input_uri":"/tmp/sample.txt","target_format":"md","mode":"normal"}'
```

## 10. 日志

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

文件转换日志还会出现：

- `source_format`
- `target_format`

如果调用方传 `X-Request-ID`，响应头和日志都会带同一个值。

## 11. 升级流程

以后只要代码变了，就重复这套流程：

1. 在本地确认服务器架构对应的平台
2. 用对应 `--platform` 重新 build
3. `docker save` 导出新 tar
4. `scp` 上传到服务器
5. 服务器执行 `docker load`
6. 删除旧容器并重新 `docker run -d ...`
7. 检查 `/ready`
8. 用 `curl` 测 `export_document` 和 `convert_file_document`

如果只是修改环境变量，不改代码，则不需要重新 build 镜像，只需要在服务器上重建容器。

## 12. 部署注意点

- 不建议裸跑 `docker run -d -p 8000:8000 format-export-mcp:latest`，因为没有挂载目录和自动重启。
- 生产环境建议放在 Nginx 或平台网关后面，不建议容器端口直接暴露公网。
- 当前服务没有 Token 鉴权，至少应限制网络访问范围，并保留限流。
- 升级镜像前确认宿主机挂载目录不变，避免历史导出文件看起来“丢失”。
