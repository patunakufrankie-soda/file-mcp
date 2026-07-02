# 文档转换系统开发进度

## 🎯 项目目标

从通用格式转换转向"PDF ↔ Word 高保真转换 + 文档智能识别"

---

## ✅ 阶段一：补齐运行环境和基础转换链路（已完成）

### 1. LibreOffice 安装 ✓
- 已安装 LibreOffice 26.2.4.2
- 命令行工具 `soffice` 可用
- 测试通过：DOCX → PDF 转换成功（4.58秒）

### 2. 统一转换日志系统 ✓
**文件**: `format_export_mcp/conversion/services/conversion_logger.py`

**功能**:
- `ConversionLog`: 统一日志数据结构
  - 基础信息：时间戳、源格式、目标格式
  - 引擎信息：引擎名称、版本
  - 文件信息：源文件、输出文件、文件大小
  - 性能指标：转换耗时
  - 结果：成功/失败、错误信息、是否使用 fallback
  - 质量指标：质量等级、页数对比、文本完整率、图片/表格数量对比
  - 特征分析：源文档特征
  - 元数据：扩展字段

- `ConversionLoggerService`: 日志记录服务
  - 控制台日志输出（带格式化）
  - JSON 格式日志文件持久化

**日志示例**:
```json
{
  "timestamp": "2026-07-01T15:35:02.377401",
  "source_format": "docx",
  "target_format": "pdf",
  "engine_name": "LibreOffice",
  "duration_seconds": 4.58,
  "success": true,
  "quality_level": "high",
  "source_size_bytes": 36647,
  "output_size_bytes": 16427
}
```

### 3. 增强 PDF 识别能力 ✓
**文件**: `format_export_mcp/conversion/services/format_detector.py`

**升级内容**:

#### DocumentFeatures 数据结构增强
- ✓ `image_count`: 图片数量
- ✓ `table_count`: 表格数量（启发式检测）
- ✓ `text_block_count`: 文本块数量
- ✓ `text_coverage_ratio`: 文本覆盖率 (0.0-1.0)
- ✓ `has_multipage`: 是否多页文档
- ✓ `analysis_method`: 分析方法（pymupdf_deep / fallback / text_format）
- ✓ `analysis_confidence`: 分析置信度（high / medium / low）
- ✓ `detected_format`: 检测到的格式

#### PDF 深度分析 (`_analyze_pdf`)
- ✓ 文本层检测：提取文本内容，判断是否存在文本层
- ✓ 扫描型 PDF 识别：文本长度 < 50 视为扫描型
- ✓ 图片数量统计：`page.get_images()`
- ✓ 文本块统计：`page.get_text("blocks")`
- ✓ 多栏布局检测：文本块宽度 < 页面宽度 60% 的比例
- ✓ 表格检测（启发式）：文本块密度判断
- ✓ 文本覆盖率计算
- ✓ 复杂度评分系统：
  - 页数 > 10: +1
  - 页数 > 50: +1
  - 多栏布局: +1
  - 图片 > 5: +1
  - 有表格: +1
  - 扫描型: +2
  - 评分 ≥ 4: complex
  - 评分 ≥ 2: moderate
  - 评分 < 2: simple

**日志输出示例**:
```
INFO: PDF analysis: 1 pages, 0 images, 3 text blocks, complexity=simple, scanned=False
```

### 4. 集成转换服务 ✓
**文件**: `format_export_mcp/conversion/services/conversion_service.py`

**增强内容**:
- ✓ 集成 `ConversionLoggerService`
- ✓ 转换全流程日志记录（开始/结束/耗时）
- ✓ 源文档特征记录到日志
- ✓ Fallback 引擎标记
- ✓ 质量评估系统 (`evaluate_quality`)

#### QualityReport 结构
- `level`: high / medium / low / fallback
- `score`: 0-100
- `issues`: 问题列表
- `page_count_match`: 页数是否匹配
- `text_completeness`: 文本完整率
- `image_count_match`: 图片数是否匹配
- `table_count_match`: 表格数是否匹配

#### 质量评估逻辑
- 页数不匹配: -20 分
- 图片数不匹配: -15 分
- 表格数不匹配: -15 分
- 文本完整率 < 80%: -20 分
- 分数 ≥ 90: high
- 分数 ≥ 70: medium
- 分数 ≥ 50: low
- 分数 < 50: fallback

### 5. 异常场景测试 ✓
**测试文件**: `test_enhanced_conversion.py`

**覆盖场景**:
- ✓ 不存在的文件
- ✓ 不支持的转换路由
- ✓ LibreOffice 转换（DOCX → PDF）
- ✓ 日志记录验证
- ✓ 质量评估验证

**测试结果**:
```
✓ DOCX → PDF: 成功，4.58秒，质量=high
✓ 非法文件: 正确返回错误
✓ 不支持路由: 正确返回错误
✓ 日志记录: JSON 格式完整
```

---

## 🔄 阶段二：增强 PDF 类型识别能力（进行中）

### 当前状态
- ✅ PDF 深度分析已实现
- ✅ 动态路由基础已准备（router 支持 features 参数）
- ⏸️ 根据分析结果动态选择转换路由（待实现）

### 待实现功能
1. **动态路由选择**
   - 文本型 PDF → 使用 PyMuPDF 直接提取
   - 扫描型 PDF → 路由到 OCR 引擎
   - 复杂版式 PDF → 路由到 pdf2docx 或 LibreOffice
   - 简单版式 PDF → 使用 LayoutIR 保留结构

2. **OCR 引擎集成**（扫描型 PDF）
   - 候选方案：Tesseract OCR / PaddleOCR / EasyOCR
   - 接入点：新增 `OcrEngine` 类

3. **pdf2docx 集成**（复杂版式）
   - 用于保留复杂版式的 PDF → DOCX 转换
   - 作为 PyMuPDF 的高保真 fallback

---

## 📋 阶段三：PDF → DOCX 多策略转换（待实现）

### 策略一：文本型 PDF
- PyMuPDF 提取文字/图片/表格
- python-docx 重建 Word 文档
- 适用场景：简单文本文档，无复杂版式

### 策略二：简单版式 PDF
- LayoutIR 保留页面结构
- 记录段落位置、图片位置
- 重建时保持坐标关系

### 策略三：复杂版式 PDF
- pdf2docx 或 LibreOffice 作为 fallback
- 适用场景：多栏、复杂表格、混合布局

### 策略四：扫描型 PDF
- OCR 识别文字
- 生成可编辑 Word
- 可选保留原图作为背景

### 策略五：极复杂 PDF
- "图片型 Word" 兜底
- 每页转为图片插入 Word
- 优先保证视觉一致性

---

## 📐 阶段四：完善 IR 中间层（待实现）

### DocumentIR（语义结构）
- 标题（level 1-6）
- 段落
- 列表（有序/无序）
- 表格
- 图片
- 元数据

### LayoutIR（版式结构）
- 页面尺寸
- 文本块坐标 (x, y, width, height)
- 图片块坐标
- 表格区域坐标
- 栏数和栏宽
- 边距和间距

### 重建流程
```
PDF → PyMuPDF 分析 → LayoutIR → 重建引擎 → DOCX
                   ↓
              DocumentIR
```

---

## 📊 阶段五：转换质量评估（部分完成）

### 已实现 ✓
- ✅ 页数对比
- ✅ 文本完整率对比
- ✅ 图片数量对比
- ✅ 表格数量对比
- ✅ 质量等级分类（high/medium/low/fallback）

### 待增强
- ⏸️ 版式相似度评分
- ⏸️ 字体保留率
- ⏸️ 颜色保留率
- ⏸️ 视觉对比（截图 diff）

---

## 🛠️ 技术栈

### 已集成
- **PyMuPDF (fitz)**: PDF 分析和文本提取 ✓
- **LibreOffice**: Office 文档转换 ✓
- **python-docx**: Word 文档生成 ✓
- **Markdown 引擎**: MD ↔ 其他格式 ✓

### 待集成
- **pdf2docx**: 高保真 PDF → DOCX
- **Tesseract OCR** / **PaddleOCR**: 扫描型 PDF 识别
- **pdfplumber**: 表格精确提取（可选）
- **Pillow**: 图片处理和"图片型 Word"生成

---

## 📈 下一步行动

### 立即执行（优先级 P0）
1. ✅ 完成阶段一所有功能
2. 🔄 实现基于特征的动态路由选择
3. ⏳ 集成 pdf2docx 作为复杂版式 fallback
4. ⏳ 实现 PDF → DOCX 基础策略（文本型）

### 短期目标（优先级 P1）
1. 集成 OCR 引擎处理扫描型 PDF
2. 完善 LayoutIR 中间层
3. 实现"图片型 Word"兜底方案

### 中期目标（优先级 P2）
1. DocumentIR 语义结构完整实现
2. 基于 IR 的统一重建框架
3. 增强质量评估（视觉对比）

---

## 📝 测试覆盖

### 单元测试
- ✅ PDF 分析功能
- ✅ LibreOffice 转换
- ✅ 日志记录
- ✅ 异常处理

### 集成测试
- ⏸️ 端到端转换流程
- ⏸️ Fallback 引擎切换
- ⏸️ 质量评估准确性

### 性能测试
- ⏸️ 大文件转换（>100MB）
- ⏸️ 多页文档（>100页）
- ⏸️ 并发转换压力测试

---

## 🎉 里程碑

- **2026-07-01**: 
  - ✅ LibreOffice 安装完成
  - ✅ 统一日志系统实现
  - ✅ PDF 深度分析完成
  - ✅ 质量评估基础框架
  - ✅ 阶段一完成

---

## 📚 参考资源

- [PyMuPDF 文档](https://pymupdf.readthedocs.io/)
- [LibreOffice 命令行参考](https://help.libreoffice.org/latest/en-US/text/shared/guide/start_parameters.html)
- [pdf2docx GitHub](https://github.com/dothinking/pdf2docx)
- [python-docx 文档](https://python-docx.readthedocs.io/)
