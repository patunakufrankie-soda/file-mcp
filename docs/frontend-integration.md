# Format Export MCP 前端接入说明

本文档面向前端接入同事，说明如何调用导出接口、处理返回结果、下载文件和排查常见错误。

## 1. 接口地址

HTTP 辅助导出接口：

```text
POST /api/export_document
```

HTTP 文档转换接口：

```text
POST /api/convert_document
```

文件下载接口：

```text
GET /downloads/{file_name}
```

本地联调默认地址：

```text
http://127.0.0.1:8000
```

如果本地 `8000` 被占用，后端可能会改成 `8001` 或其他端口，前端只需要调整 base URL。

## 2. 支持格式

当前支持：

```text
pdf, docx, xlsx, csv, txt, md, markdown, html
```

说明：

- `markdown` 会按 `md` 导出，最终文件扩展名是 `.md`
- 旧版 `doc` 和 `xls` 不再支持
- `xlsx` 和 `csv` 当前把 `content` 当作 CSV 风格文本解析
- 当前不支持上传已有 `pdf/docx/xlsx` 再互转格式
- 如果导出内容包含图片，则只支持 `pdf` 和 `docx`
- 如果 `content` 是 Markdown，大模型输出里的标题、列表、代码块在 `pdf/docx/html` 中会按结构渲染
- 专门的文档转换接口当前只支持：`markdown/text -> pdf`、`markdown/text -> docx`、`csv -> xlsx`

## 3. 请求参数

```json
{
  "title": "会议纪要",
  "content": "一、会议主题：...\n二、会议结论：...",
  "images": [],
  "format": "pdf"
}
```

字段说明：

- `title`：文件标题，也会参与生成文件名
- `content`：导出内容
- `images`：可选图片列表，支持 `data:image/...;base64,...` 或本地图片路径
- `format`：目标格式

这三个字段都应传字符串。`null`、数字、对象等非字符串值会返回 `400`。
`images` 如果传入，必须是字符串数组；只要数组非空，`format` 就只能是 `pdf` 或 `docx`。

## 4. 成功响应

```json
{
  "success": true,
  "file_name": "会议纪要-a1b2c3d4.pdf",
  "file_url": "/downloads/会议纪要-a1b2c3d4.pdf"
}
```

响应头会包含：

```text
X-Request-ID: <request-id>
```

前端可直接使用 `file_url` 触发下载。

## 5. 错误响应

错误响应统一为：

```json
{
  "success": false,
  "request_id": "req-xxx",
  "error": {
    "code": "invalid_request",
    "message": "format must be a string"
  }
}
```

常见错误码：

- `invalid_request`：参数错误或不支持的格式
- `rate_limited`：请求过于频繁，HTTP 状态码 `429`
- `storage_error`：后端存储不可用或写入失败
- `internal_error`：未知内部错误

排障时把 `request_id` 提供给后端即可查日志。

## 6. 推荐调用方式

```ts
type ExportFormat = "pdf" | "docx" | "xlsx" | "csv" | "txt" | "md" | "markdown" | "html";

type ExportSuccess = {
  success: true;
  file_name: string;
  file_url: string;
};

type ExportFailure = {
  success: false;
  request_id?: string;
  error?: {
    code: string;
    message: string;
  };
};

type ExportResult = ExportSuccess | ExportFailure;

export async function exportDocument(params: {
  title: string;
  content: string;
  images?: string[];
  format: ExportFormat;
}): Promise<ExportSuccess> {
  const requestId = crypto.randomUUID();

  const response = await fetch("/api/export_document", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Request-ID": requestId,
    },
    body: JSON.stringify(params),
  });

  const result = (await response.json()) as ExportResult;

  if (!response.ok || !result.success) {
    const message = !result.success && result.error
      ? result.error.message
      : "导出失败，请稍后重试";
    throw new Error(message);
  }

  return result;
}
```

如果要走专门的文档转换接口：

```ts
type ConvertSourceFormat = "markdown" | "md" | "text" | "txt" | "csv";
type ConvertTargetFormat = "pdf" | "docx" | "xlsx";

export async function convertDocument(params: {
  title: string;
  source_format: ConvertSourceFormat;
  target_format: ConvertTargetFormat;
  content: string;
}): Promise<ExportSuccess> {
  const requestId = crypto.randomUUID();

  const response = await fetch("/api/convert_document", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Request-ID": requestId,
    },
    body: JSON.stringify(params),
  });

  const result = (await response.json()) as ExportResult;

  if (!response.ok || !result.success) {
    const message = !result.success && result.error
      ? result.error.message
      : "转换失败，请稍后重试";
    throw new Error(message);
  }

  return result;
}
```

## 7. 触发下载

简单方式：

```ts
const result = await exportDocument({
  title: "会议纪要",
  content: "这里是内容",
  images: [],
  format: "pdf",
});

window.location.href = result.file_url;
```

如果需要保留当前页面状态，可以创建临时链接：

```ts
const link = document.createElement("a");
link.href = result.file_url;
link.download = result.file_name;
document.body.appendChild(link);
link.click();
link.remove();
```

如果后端部署在独立域名或端口，需要拼接 base URL：

```ts
const baseUrl = "http://127.0.0.1:8000";
window.location.href = `${baseUrl}${result.file_url}`;
```

## 8. 格式菜单示例

```ts
export const exportOptions = [
  { label: "PDF", format: "pdf" },
  { label: "Word", format: "docx" },
  { label: "Excel", format: "xlsx" },
  { label: "CSV", format: "csv" },
  { label: "TXT", format: "txt" },
  { label: "Markdown", format: "md" },
  { label: "HTML", format: "html" },
] as const;
```

## 9. 表格导出注意点

`csv` 和 `xlsx` 当前适合传 CSV 风格文本：

```ts
const content = [
  "姓名,部门,备注",
  '张三,研发,"包含逗号,也可以"',
  "李四,产品,普通文本",
].join("\n");

await exportDocument({
  title: "人员表",
  content,
  images: [],
  format: "xlsx",
});
```

图片导出示例：

```ts
await exportDocument({
  title: "AI 图片结果",
  content: "以下是本次生成结果",
  images: ["data:image/png;base64,..."],
  format: "docx",
});
```

如果后续需要复杂表格、多 sheet、单元格样式，建议扩展后端输入结构，不建议前端继续拼复杂 CSV 文本。

## 10. 联调检查

后端服务存活：

```bash
curl http://127.0.0.1:8000/health
```

后端存储可写：

```bash
curl http://127.0.0.1:8000/ready
```

接口导出测试：

```bash
curl -X POST http://127.0.0.1:8000/api/export_document \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: frontend-test-001" \
  -d '{"title":"前端联调","content":"hello","format":"txt"}'
```

文档转换测试：

```bash
curl -X POST http://127.0.0.1:8000/api/convert_document \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: frontend-convert-001" \
  -d '{"title":"市场分析","source_format":"markdown","target_format":"pdf","content":"# 标题\n\n1.**数字化转型加速**：内容"}'
```

## 11. 前端需要注意

- 不要传 `doc` 或 `xls`，后端已经移除旧版格式。
- 不要把 `null`、数字或对象传给 `title/content/format`。
- 不要上传已有 Office/PDF 文件要求后端互转格式；当前服务支持文本导出，以及把图片嵌入 `pdf/docx`。
- 不要在 `txt/md/csv/xlsx/html` 导出请求里传图片，后端会直接返回参数错误。
- 不要把 `/api/convert_document` 理解成文件上传转换，它当前只接受文本内容和格式对。
- `csv -> pdf`、`pdf -> docx`、`docx -> pdf` 这类转换当前都不支持，会返回 `invalid_request`。
- 遇到 `429` 时可以提示“导出过于频繁，请稍后再试”。
- 遇到 `storage_error` 或 `internal_error` 时展示通用失败提示，并把 `request_id` 给后端排查。
- 如果文件下载 404，通常是文件已过期清理、下载前缀不对，或前端拼接了错误 base URL。
- 如果前端页面和导出服务跨域部署，后端必须配置 `FORMAT_EXPORT_ALLOWED_ORIGINS`，否则浏览器预检 `OPTIONS` 会失败。
