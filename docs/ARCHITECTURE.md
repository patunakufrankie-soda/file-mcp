# Format Export MCP Architecture

## Overview

这个仓库现在稳定在两条主线：

- `export/`: 把文本内容导出为目标文件格式
- `conversion/`: 把已有文件在受支持格式之间互转

两条主线共用同一套传输层、存储层和工具层。

## Directory layout

```text
format_export_mcp/
├── mcp/
│   └── tools.py
├── export/
│   ├── service.py
│   └── generators/
├── conversion/
│   ├── file_document_convert.py
│   ├── conversion_matrix.py
│   ├── router.py
│   ├── engines/
│   ├── ir/
│   └── services/
├── storage/
│   └── manager.py
├── utils/
├── server_common.py
├── server_stdio.py
├── server_sse.py
└── server_streamable_http.py
```

## Layers

### Transport layer

- `server_stdio.py`
- `server_sse.py`
- `server_streamable_http.py`
- `server_common.py`

这几个入口共享同一个 MCP 定义和同一组 HTTP 辅助路由，只是暴露协议不同。

### MCP tool layer

- `mcp/tools.py`

这里保留对外稳定的 tool 接口：

- `export_document`
- `convert_file_document`
- `get_supported_conversions`

### Export module

- `export/service.py`
- `export/generators/*.py`

`export/service.py` 负责参数编排、目标路径和生成器分发。各生成器只关心单一输出格式，比如 PDF、DOCX、XLSX、CSV、TXT、MD、HTML。

### Conversion module

- `conversion/file_document_convert.py`
- `conversion/router.py`
- `conversion/services/*.py`
- `conversion/engines/*.py`
- `conversion/ir/*.py`

转换链路先加载输入文件，再做格式检测和特征分析，接着经由路由器选择主引擎和 fallback 引擎。

当前重要的引擎职责：

- `PdfEngine`: PDF -> TXT/MD
- `MarkdownEngine`: MD/TXT -> PDF/DOCX/HTML/TXT/MD
- `LibreOfficeEngine`: Office -> PDF，以及同族 Office 互转
- `PdfToDocxEngine`: 偏可编辑性的 PDF -> DOCX
- `Pdf2DocxEngine`: 偏版式保留的 PDF -> DOCX fallback

### Storage and utility layers

- `storage/manager.py`
- `utils/*.py`

存储层统一处理导出目录和文件路径。工具层负责输入加载、Markdown 解析、图片获取、表格辅助和错误工具。

## Runtime flow

### `export_document`

1. 接收标题、内容、图片和目标格式
2. 由 `export/service.py` 选择生成器
3. 生成文件并写入导出目录
4. 返回 `file_name` 和 `file_url`

### `convert_file_document`

1. 加载本地文件路径或远程 URL
2. 检测源格式
3. 分析文档特征
4. 由 `ConversionRouter` 选择引擎
5. 执行主引擎，必要时走 fallback
6. 产出本地输出路径和下载 URL

## Design notes

- 传输协议和业务逻辑解耦：协议变了，不影响 export 和 conversion 模块
- 一个路由 seam 后面可以放多个 adapter：这就是 `PdfToDocxEngine` 和 `Pdf2DocxEngine` 共存的原因
- 存储路径和公共 URL 都由配置驱动，调用方不需要了解底层目录结构
- `conversion/ir/` 现在更多是为复杂转换和后处理预留，不是每条链路都必须经过它
