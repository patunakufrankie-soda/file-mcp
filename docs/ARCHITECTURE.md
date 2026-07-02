# 项目架构重构完成

## 新的目录结构

```
format_export_mcp/
├── mcp/                              # MCP 工具层（对外接口）
│   ├── __init__.py
│   └── tools.py                      # MCP tool 定义，调用下层服务
│
├── export/                           # Format Export 功能（Markdown → 各种格式）
│   ├── __init__.py
│   ├── service.py                    # 导出服务，编排生成器
│   └── generators/                   # 格式生成器
│       ├── __init__.py
│       ├── pdf_generator.py          # MD → PDF
│       ├── docx_generator.py         # MD → DOCX
│       ├── xlsx_generator.py         # MD → XLSX
│       ├── csv_generator.py          # MD → CSV
│       ├── txt_generator.py          # MD → TXT
│       ├── html_generator.py         # MD → HTML
│       └── md_generator.py           # MD → MD (直接输出)
│
├── conversion/                       # Document Conversion 功能（文档互转）
│   ├── __init__.py
│   ├── file_document_convert.py      # 当前实现（待重构为使用 ConversionService）
│   ├── conversion_matrix.py          # 支持的转换矩阵
│   │
│   ├── services/                     # 服务层（业务编排）
│   │   ├── __init__.py
│   │   ├── conversion_service.py     # 转换编排服务
│   │   └── format_detector.py        # 格式检测与特征分析
│   │
│   ├── engines/                      # 转换引擎层
│   │   ├── __init__.py
│   │   ├── base.py                   # 引擎基类
│   │   ├── libreoffice_engine.py     # LibreOffice 引擎（待实现）
│   │   ├── pdf_engine.py             # PDF 引擎（待实现）
│   │   ├── ocr_engine.py             # OCR 引擎（待实现）
│   │   └── markdown_engine.py        # Markdown 引擎（待实现）
│   │
│   └── ir/                           # 中间表示层
│       ├── __init__.py
│       ├── document_ir.py            # 语义层 IR（内容结构）
│       └── layout_ir.py              # 版式层 IR（布局定位，预留）
│
├── storage/                          # 统一存储层
│   ├── __init__.py
│   ├── manager.py                    # 文件存储管理
│   └── exports/                      # 导出文件目录
│
├── utils/                            # 公共工具
│   ├── __init__.py
│   ├── format_utils.py               # 格式工具
│   ├── command_utils.py              # 命令行工具
│   ├── image_sources.py              # 图片加载
│   ├── markdown_blocks.py            # Markdown 解析
│   ├── tabular.py                    # 表格解析
│   └── input_loader.py               # 输入文件加载
│
└── server_*.py                       # MCP 服务器入口
    ├── server_common.py              # 公共服务定义
    ├── server_stdio.py               # stdio 协议
    ├── server_sse.py                 # SSE 协议
    └── server_streamable_http.py     # HTTP 协议
```

## 两大功能模块

### 1. Format Export（export/）
**用途**: 大模型输出内容导出  
**输入**: Markdown 文本（AI 生成内容）  
**输出**: PDF/DOCX/XLSX/CSV/TXT/HTML  
**架构**: 简单编排，直接调用生成器  
**MCP Tool**: `export_document`

### 2. Document Conversion（conversion/）
**用途**: 文档格式互转  
**输入**: 任意格式文档文件  
**输出**: 其他格式  
**架构**: 多引擎 + 路由 + IR + fallback  
**MCP Tool**: `convert_file_document`

## 技术栈（已规划）

### 转换引擎
- **LibreOffice**: Office 格式 ↔ PDF
- **FreeP2W / pdf2docx**: PDF → DOCX
- **PyMuPDF**: PDF → TXT/MD、结构提取
- **pdfplumber**: PDF 表格提取
- **OCRmyPDF / PaddleOCR**: 扫描型 PDF
- **python-docx**: DOCX 重建和后处理

## 下一步工作

### 第一阶段：完善当前实现
1. ✅ 重构目录结构
2. ✅ 创建引擎基类和 IR 层接口
3. ✅ 创建 ConversionService 和 FormatDetector
4. ⏳ 将 `file_document_convert.py` 重构为使用 ConversionService
5. ⏳ 实现第一个引擎（建议从 PyMuPDF 开始）

### 第二阶段：引擎实现
6. 实现 PDF 引擎（PyMuPDF + pdfplumber）
7. 实现 LibreOffice 引擎
8. 实现 OCR 引擎
9. 实现 FreeP2W 引擎
10. 完善路由表和 fallback 机制

### 第三阶段：优化
11. 完善 IR 层实现
12. 添加后处理和质量评估
13. 性能优化和错误处理
14. 单元测试和集成测试

## 核心设计原则

1. **MCP 层纯净**: 只做参数校验和转发
2. **服务层编排**: 业务逻辑在 Service 层
3. **引擎独立**: 每个引擎自包含，可独立测试
4. **IR 统一**: 所有引擎输出映射到统一结构
5. **存储透明**: 上层不关心文件存储细节

## 验证状态

✅ 目录结构创建完成  
✅ 所有模块可正常导入  
✅ MCP 服务器启动正常  
⏳ 引擎实现待完成  
⏳ 路由表待配置
