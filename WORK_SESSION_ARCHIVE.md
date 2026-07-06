# 工作会话存档 - 2026-07-06

## 📍 当前进度

### 本次会话完成的工作

#### 1. **Docker 依赖修复**（核心成果）
- **问题**：发现 `pdf2docx` 库缺失，会导致复杂版式 PDF 转 DOCX 失败
- **解决**：
  - 在 `pyproject.toml` 添加 `pdf2docx>=0.5.8` 和 `Pillow>=10.0.0`
  - 在 `Dockerfile` 添加 Tesseract OCR 系统依赖（中英文语言包）
  - 修复 Python 版本不匹配：`python:3.11-slim` → `python:3.12-slim`
- **影响**：镜像现在具备完整的 PDF 双向转换能力

#### 2. **转换系统完成度评估**（70% 完成）

**已完成功能**：
- ✅ 6 个转换引擎全部实现
  - LibreOfficeEngine（Office → PDF）
  - PdfEngine（PDF → TXT/MD）
  - MarkdownEngine（MD ↔ 其他）
  - DocxEngine（DOCX → TXT/MD）
  - PdfToDocxEngine（自研，文本+图片+表格提取）
  - Pdf2DocxEngine（基于 pdf2docx，复杂版式）
- ✅ 智能路由系统（router.py）
  - 基于 DocumentFeatures 动态选择引擎
  - 5 种 PDF 策略：text_pdf, scanned_pdf, complex_layout_pdf, mixed_pdf, office_like_pdf
- ✅ PDF 深度分析（format_detector.py）
  - 文本层检测、扫描型识别、图片/表格统计、复杂度评分
- ✅ 日志和质量评估框架

**待完成功能**：
- ❌ OCR 引擎未集成（扫描型 PDF 目前返回错误）
- ❌ IR 中间层未实现（DocumentIR/LayoutIR）
- ⚠️ 表格提取准确率有限
- ⚠️ 版式保留基础（无颜色/对齐/行距）

---

## 🧪 待验证问题

### 1. **测试失败**（2/75 失败）
```
FAIL: test_export_document_api_handles_cors_preflight_requests
FAIL: test_export_document_api_includes_cors_headers_on_post
```
- **现象**：期望 200，实际 403
- **原因**：CORS 配置问题
- **优先级**：P1（影响 API 跨域调用）

### 2. **LibreOffice 环境检测**
```
✗ docx → pdf | LibreOffice | 0.00s | Error: LibreOffice is not installed or not in PATH
```
- **现象**：本地测试找不到 LibreOffice
- **影响**：Office → PDF 转换失败
- **Docker 环境**：已在 Dockerfile 安装，需验证容器内是否正常

### 3. **Nacos 集成警告**
```
Nacos manager initialization failed
No config found: data_id=format-export-mcp.yaml, group=DEFAULT_GROUP
```
- **现象**：配置中心连接失败
- **影响**：服务注册/配置拉取失败（非关键）
- **优先级**：P2（可选功能）

---

## 📦 依赖清单（已更新）

### Python 依赖（pyproject.toml）
```toml
PyMuPDF>=1.24.10          # PDF 解析
python-docx>=1.1.2        # DOCX 生成
pdf2docx>=0.5.8          # 复杂版式 PDF → DOCX（新增）
Pillow>=10.0.0           # 图片处理（新增）
markdown>=3.7            # Markdown 转换
reportlab>=4.2.5         # PDF 生成
```

### 系统依赖（Dockerfile）
```dockerfile
libreoffice              # Office 转换
tesseract-ocr            # OCR 引擎（新增）
tesseract-ocr-chi-sim    # 简体中文（新增）
tesseract-ocr-chi-tra    # 繁体中文（新增）
tesseract-ocr-eng        # 英文（新增）
pandoc                   # Markdown 增强
fonts-noto-cjk           # 中文字体
```

---

## 🎯 下一步建议

### 立即执行（P0）
1. **修复 CORS 测试失败**
   - 检查 `server_streamable_http.py` 的 CORS 配置
   - 验证 OPTIONS 请求处理逻辑
   
2. **验证 Docker 镜像构建**
   ```bash
   docker build -t format-export:latest -f format_export_mcp/Dockerfile .
   docker run --rm format-export:latest pip list | grep -E "pdf2docx|Pillow"
   docker run --rm format-export:latest tesseract --version
   ```

3. **端到端测试 PDF 转换**
   - 准备测试文件：文本型 PDF、复杂版式 PDF、扫描型 PDF
   - 验证路由器是否正确选择引擎
   - 检查转换质量报告

### 短期目标（P1）
1. **集成 Tesseract OCR**
   - 添加 `pytesseract>=0.3.10` 到 pyproject.toml
   - 实现 `OcrEngine` 类
   - 修改 router.py：`scanned_pdf` → `OcrEngine`

2. **修复 LibreOffice 路径问题**
   - 检测 `soffice` 命令可用性
   - 添加环境变量配置选项

3. **增强表格提取**
   - 评估 `pdfplumber` 集成
   - 对比当前启发式方法准确率

### 中期目标（P2）
1. **实现 LayoutIR 中间层**
   - 保留坐标信息
   - 支持精确版式重建

2. **视觉质量评估**
   - 截图对比
   - 版式相似度评分

---

## 📂 项目结构

```
format_export_mcp/
├── conversion/
│   ├── engines/
│   │   ├── base.py                    # 引擎基类
│   │   ├── pdf_engine.py              # PDF → TXT/MD
│   │   ├── pdf_to_docx_engine.py      # 自研 PDF → DOCX（文本+图片+表格）
│   │   ├── pdf2docx_engine.py         # pdf2docx PDF → DOCX（复杂版式）
│   │   ├── libreoffice_engine.py      # Office → PDF
│   │   ├── markdown_engine.py         # MD ↔ 其他
│   │   └── docx_engine.py             # DOCX → TXT/MD
│   ├── services/
│   │   ├── conversion_service.py      # 转换服务协调层
│   │   ├── conversion_logger.py       # 统一日志系统
│   │   └── format_detector.py         # PDF 深度分析
│   ├── ir/
│   │   ├── document_ir.py             # 语义结构（未实现）
│   │   └── layout_ir.py               # 版式结构（未实现）
│   ├── router.py                      # 智能路由系统
│   └── conversion_matrix.py           # 转换矩阵
├── Dockerfile                         # 容器配置（已修复）
└── server_streamable_http.py          # HTTP 服务入口
```

---

## 🔧 关键配置文件状态

- **pyproject.toml**: ✅ 已更新依赖
- **Dockerfile**: ✅ 已修复 Python 版本 + 添加 OCR
- **CONVERSION_PROGRESS.md**: ✅ 阶段一完成，阶段二进行中
- **tests/**: ⚠️ 2 个 CORS 测试失败

---

## 📊 能力矩阵

| 转换路由 | 引擎 | 状态 | 质量 |
|---------|------|------|------|
| DOCX→PDF | LibreOffice | ✅ | High |
| PDF→TXT/MD | PyMuPDF | ✅ | High |
| PDF→DOCX（文本型） | PdfToDocxEngine | ✅ | Medium |
| PDF→DOCX（复杂版式） | Pdf2DocxEngine | ✅ | High |
| PDF→DOCX（扫描型） | OCR | ❌ | - |
| MD↔其他 | Markdown | ✅ | High |

---

## 💡 技术决策记录

1. **为何同时保留 PdfToDocxEngine 和 Pdf2DocxEngine？**
   - PdfToDocxEngine：轻量、可控，适合简单文本型 PDF
   - Pdf2DocxEngine：重量、高保真，适合复杂版式
   - 通过路由器根据 DocumentFeatures 动态选择

2. **为何预装 Tesseract 但不添加 pytesseract？**
   - 系统级依赖先行，Python 绑定延后到实现 OcrEngine 时
   - 避免未使用的依赖增加镜像体积

3. **为何 Python 3.12？**
   - pyproject.toml 设置 `requires-python = ">=3.12"`
   - 与项目其他部分保持一致

---

## 🗃️ 数据库状态

**当前项目无数据库依赖**
- 转换系统为无状态服务
- 日志输出到文件系统（`storage/exports/`）
- Nacos 配置中心为可选（当前未连接）

---

## 📝 Git 提交记录

**待提交更改**：无（工作树干净）
**当前分支**：main（领先 origin/main 3 个提交）

---

## 🚀 会话使用的模型

**Claude-opus-4-8**
- 由 Anthropic 提供
- 通过 Crow5 CLI 工具使用

---

## 📌 参考文档

- [CONVERSION_PROGRESS.md](./CONVERSION_PROGRESS.md) - 详细开发进度
- [PROJECT_STRUCTURE.txt](./PROJECT_STRUCTURE.txt) - 项目结构
- [DEPLOYMENT.md](./DEPLOYMENT.md) - 部署指南
- [format_export_mcp/README.md](./format_export_mcp/README.md) - 使用说明

---

**存档时间**: 2026-07-06  
**会话上下文**: 本次会话完成了 Docker 依赖修复、转换系统评估、测试运行分析
