# Format Export MCP

Format Export MCP 是一个通用格式导出 MCP Server，用于把文档解析结果、会议纪要、工艺卡、AI 生成内容、知识库问答结果、周报等内容统一导出为文件。

它不依赖大模型推理，Agent 和前端都可以调用同一个能力。

## 能力

- MCP 名称：`Format Export MCP`
- Tool 名称：`export_document`
- 支持格式：`pdf`、`docx`、`xlsx`、`csv`、`txt`、`md`、`html`
- 传输方式：`stdio`、`sse`、`streamable_http`
- 本地存储：`storage/exports/`
- 下载 URL：`/downloads/{file_name}`

## 目录结构

```text
format_export_mcp/
├── server_stdio.py
├── server_sse.py
├── server_streamable_http.py
├── server_common.py
├── tools/
│   ├── export_document.py
│   ├── pdf_generator.py
│   ├── docx_generator.py
│   ├── txt_generator.py
│   ├── md_generator.py
│   ├── html_generator.py
│   └── storage.py
├── storage/
│   └── exports/
├── Dockerfile
└── README.md
```

`tools/export_document.py` 是业务入口，三个 `server_*.py` 只负责切换传输协议。依赖统一维护在根目录 `pyproject.toml`，后续新增格式或更换存储目录，不需要改传输层代码。

## uv 安装

```bash
cd /path/to/project
uv sync
```

也可以不显式同步，直接用 `uv run` 启动，uv 会根据根目录 `pyproject.toml` 自动创建环境并安装依赖。

## Tool 输入

```json
{
  "title": "会议纪要",
  "content": "这里是需要导出的内容",
  "format": "pdf"
}
```

`format` 可传：`pdf`、`docx`、`xlsx`、`csv`、`txt`、`md`、`markdown`、`html`。

## Tool 返回

```json
{
  "success": true,
  "file_name": "会议纪要-a1b2c3d4.pdf",
  "file_url": "/downloads/会议纪要-a1b2c3d4.pdf"
}
```

## MCP Tool 注册代码

Tool 注册集中在 `server_common.py`：

```python
from fastmcp import FastMCP
from format_export_mcp.tools.export_document import export_document

mcp = FastMCP("Format Export MCP")

@mcp.tool(name="export_document")
def export_document_tool(title: str, content: str, format: str):
    return export_document(title=title, content=content, format=format)
```

当前工程还注册了三个 HTTP 辅助路由：

- `GET /health`
- `GET /ready`
- `POST /api/export_document`
- `GET /downloads/{file_name}`

这些路由由 FastMCP 的 `custom_route` 提供，没有使用 FastAPI。

## stdio 启动

```bash
uv run format-export-stdio
```

等价模块启动方式：

```bash
uv run python -m format_export_mcp.server_stdio
```

Agent 平台配置示例：

```json
{
  "mcpServers": {
    "format-export": {
      "command": "uv",
      "args": ["run", "format-export-stdio"],
      "cwd": "/path/to/project"
    }
  }
}
```

## SSE 启动

```bash
uv run format-export-sse
```

等价模块启动方式：

```bash
uv run python -m format_export_mcp.server_sse
```

SSE MCP 地址通常为：

```text
http://127.0.0.1:8000/sse/
```

## Streamable HTTP 启动

```bash
uv run format-export-http
```

等价模块启动方式：

```bash
uv run python -m format_export_mcp.server_streamable_http
```

Streamable HTTP MCP 地址：

```text
http://127.0.0.1:8000/mcp/
```

## Agent 调用示例

用户：

```text
帮我生成会议纪要并导出 PDF
```

Agent 调用 MCP Tool：

```json
{
  "tool": "export_document",
  "arguments": {
    "title": "会议纪要",
    "content": "一、会议主题：...\n二、会议结论：...",
    "format": "pdf"
  }
}
```

返回：

```json
{
  "success": true,
  "file_name": "会议纪要-a1b2c3d4.pdf",
  "file_url": "/downloads/会议纪要-a1b2c3d4.pdf"
}
```

## 前端调用示例

如果前端通过公司平台的 MCP Client 调用，直接调用 `export_document` Tool 即可。

如果前端希望通过 HTTP JSON 调用辅助路由：

```ts
async function exportDocument(
  format: "pdf" | "docx" | "xlsx" | "csv" | "txt" | "md" | "html"
) {
  const response = await fetch("/api/export_document", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: "会议纪要",
      content: "这里是需要导出的内容",
      format
    })
  });

  const result = await response.json();
  if (result.success) {
    window.location.href = result.file_url;
  }
}
```

页面菜单可以统一映射：

```ts
const exportOptions = [
  { label: "TXT", format: "txt" },
  { label: "CSV", format: "csv" },
  { label: "DOCX", format: "docx" },
  { label: "XLSX", format: "xlsx" },
  { label: "PDF", format: "pdf" },
  { label: "Markdown", format: "md" },
  { label: "HTML", format: "html" }
];
```

## Docker 部署

构建镜像：

```bash
docker build -f format_export_mcp/Dockerfile -t format-export-mcp .
```

运行 Streamable HTTP：

```bash
docker run --rm -p 8000:8000 \
  -v "$(pwd)/format_export_mcp/storage/exports:/app/format_export_mcp/storage/exports" \
  format-export-mcp
```

访问：

```text
MCP: http://localhost:8000/mcp/
Health: http://localhost:8000/health
Ready: http://localhost:8000/ready
Downloads: http://localhost:8000/downloads/{file_name}
```

运行 SSE：

```bash
docker run --rm -p 8000:8000 \
  format-export-mcp \
  python -m format_export_mcp.server_sse
```

## 测试服务器部署

推荐直接使用 `docker compose`：

```bash
cd /path/to/repo
docker compose -f format_export_mcp/docker-compose.yml up -d --build
```

这会把导出目录挂到测试服务器上的 NFS 路径：

```text
/mnt/nfs/format-export/exports
```

部署后可验证：

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/
```

如果测试服务器前面要挂 Nginx，可参考 `format_export_mcp/nginx.format-export.conf`，将外部域名转到本机 `8000` 端口。

## 镜像推送与拉取

构建镜像：

```bash
docker build -f format_export_mcp/Dockerfile -t registry.company.com/platform/format-export-mcp:latest .
```

推送到镜像仓库：

```bash
docker push registry.company.com/platform/format-export-mcp:latest
```

测试服务器拉取并运行：

```bash
docker pull registry.company.com/platform/format-export-mcp:latest
docker run -d \
  --name format-export-mcp \
  --restart unless-stopped \
  -p 8000:8000 \
  -e FORMAT_EXPORT_HOST=0.0.0.0 \
  -e FORMAT_EXPORT_PORT=8000 \
  -e FORMAT_EXPORT_STORAGE_DIR=/data/format-export/exports \
  -v /mnt/nfs/format-export/exports:/data/format-export/exports \
  registry.company.com/platform/format-export-mcp:latest
```

注意：容器现在默认以非 root 用户运行，挂载到 `FORMAT_EXPORT_STORAGE_DIR` 的宿主机目录需要对容器内运行用户可写。

## Nginx 反向代理

参考配置：

```nginx
server {
    listen 80;
    server_name format-export-test.company.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

Nginx 启用后，平台侧就可以使用：

```text
http://format-export-test.company.com/mcp/
http://format-export-test.company.com/downloads/xxx.pdf
```

## NFS 存储

这套实现现在只保留 NFS / 共享文件系统这一种落地方式。生产环境里把 `FORMAT_EXPORT_STORAGE_DIR` 挂到 NFS 目录即可，导出文件会直接写到共享盘上。

- `FORMAT_EXPORT_STORAGE_DIR`：导出目录，默认 `format_export_mcp/storage/exports`
- `FORMAT_EXPORT_PUBLIC_BASE_URL`：下载前缀，默认 `/downloads`
- `FORMAT_EXPORT_FILE_TTL_SECONDS`：导出文件保留时长，默认 `604800` 秒（7 天）
- `FORMAT_EXPORT_RATE_LIMIT_PER_MINUTE`：`POST /api/export_document` 的单 IP 每分钟请求上限，默认 `20`
- `/health`：轻量 liveness，只检查进程是否存活
- `/ready`：readiness，会检查导出目录存在且当前进程可写

## 日志与排障

`POST /api/export_document` 会返回 `X-Request-ID` 响应头。调用方可以传入 `X-Request-ID` 请求头，未传时服务端会自动生成。

导出成功、失败和限流都会输出 JSON 格式日志，包含：

- `event`
- `request_id`
- `client_host`
- `status_code`
- `duration_ms`
- `error_code`（失败时）
- `file_name` 和 `format`（成功时）

## 发布制品管理

源码仓库只保留源码、配置和测试。镜像 tar、压缩包等发布制品不放在仓库根目录，也不纳入 Git 基线；发布物应交给镜像仓库、制品仓库或部署流水线管理。

推荐部署时将 `FORMAT_EXPORT_STORAGE_DIR` 指向挂载好的 NFS 路径，例如：

```bash
export FORMAT_EXPORT_STORAGE_DIR=/mnt/nfs/format-export/exports
```

返回值始终保持一致：

- `file_name`：文件名
- `file_url`：下载地址，例如 `/downloads/会议纪要-a1b2c3d4.pdf`

如果平台前面有网关或统一文件服务，可以把 `FORMAT_EXPORT_PUBLIC_BASE_URL` 改成完整域名，例如：

```bash
export FORMAT_EXPORT_PUBLIC_BASE_URL=https://files.company.com/downloads
```

## 扩展 PPTX 导出方案

新增：

- `tools/pptx_generator.py`
- 依赖：`python-pptx`
- 在 `GENERATORS` 中增加 `"pptx": ("pptx", generate_pptx)`

内容策略：

- `title` 作为封面或第一页标题
- `content` 按段落、Markdown 标题或业务结构切分为多页
- 会议纪要、周报可以按“议题、结论、待办”映射到不同版式

## 表格格式说明

- `xlsx`：当前使用项目内置 XML 打包方式生成单 sheet 文件，适合轻量导出。
- `csv`：使用 Python 标准库 `csv`，适合简单表格和跨系统交换。
- 这两类格式当前都把 `content` 视为 CSV 风格文本输入；如果后续要支持更稳定的复杂表格，建议扩展为结构化 `rows` 参数。

## 设计说明

- 业务逻辑与传输层解耦：`export_document()` 不关心 stdio、SSE 或 HTTP。
- 文件名使用标题加随机短 token，降低重名覆盖风险。
- 每次导出前会清理超过 TTL 的历史文件，避免存储目录持续膨胀。
- HTTP 导出接口会返回请求 ID，并记录结构化成功、失败和限流日志。
- PDF 使用 `reportlab` 的 CID 字体 `STSong-Light`，适配中文内容。
- DOCX 使用 `python-docx`，并设置中文字体。
- 表格导出当前聚焦 `xlsx/csv` 两种常用格式，旧版 `doc/xls` 已移除。
- 前端可走 MCP Client，也可走 HTTP 辅助路由。
- HTTP 辅助导出路由默认带单 IP 限流；如需更强保护，建议仍在网关层补鉴权和全局限流。
- 当前没有鉴权，生产环境建议在平台网关或 FastMCP 鉴权层补充 Bearer Token、租户隔离、文件过期清理和审计日志。
