#!/usr/bin/env python3
"""
集成测试：验证文档转换功能
"""

import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from format_export_mcp.conversion.file_document_convert import convert_file_document
from format_export_mcp.export.service import export_document


def test_markdown_conversion():
    """测试 Markdown 转换功能"""
    print("\n" + "=" * 60)
    print("测试 1: Markdown 文件转换")
    print("=" * 60)

    test_file = Path(__file__).parent / "test_document.md"

    if not test_file.exists():
        print("❌ 测试文件不存在")
        return False

    # Test 1: MD → TXT
    print("\n[1/3] 测试 MD → TXT...")
    result = convert_file_document(str(test_file), "txt")
    if result.get("success"):
        print(f"✅ 成功: {result.get('output_path')}")
        print(f"   URL: {result.get('output_url')}")
    else:
        print(f"❌ 失败: {result.get('message')}")
        return False

    # Test 2: MD → PDF
    print("\n[2/3] 测试 MD → PDF...")
    result = convert_file_document(str(test_file), "pdf")
    if result.get("success"):
        print(f"✅ 成功: {result.get('output_path')}")
        print(f"   URL: {result.get('output_url')}")
    else:
        print(f"❌ 失败: {result.get('message')}")
        return False

    # Test 3: MD → DOCX
    print("\n[3/3] 测试 MD → DOCX...")
    result = convert_file_document(str(test_file), "docx")
    if result.get("success"):
        print(f"✅ 成功: {result.get('output_path')}")
        print(f"   URL: {result.get('output_url')}")
    else:
        print(f"❌ 失败: {result.get('message')}")
        return False

    return True


def test_export_document():
    """测试 Export Document 功能"""
    print("\n" + "=" * 60)
    print("测试 2: Export Document (MD 内容导出)")
    print("=" * 60)

    content = """
# 测试标题

这是一段测试内容。

## 子标题

- 项目 1
- 项目 2
"""

    # Test 1: Export to PDF
    print("\n[1/3] 测试导出 PDF...")
    result = export_document("测试文档", content, "pdf")
    if result.get("success"):
        print(f"✅ 成功: {result.get('file_name')}")
        print(f"   URL: {result.get('file_url')}")
    else:
        print(f"❌ 失败")
        return False

    # Test 2: Export to DOCX
    print("\n[2/3] 测试导出 DOCX...")
    result = export_document("测试文档", content, "docx")
    if result.get("success"):
        print(f"✅ 成功: {result.get('file_name')}")
        print(f"   URL: {result.get('file_url')}")
    else:
        print(f"❌ 失败")
        return False

    # Test 3: Export to HTML
    print("\n[3/3] 测试导出 HTML...")
    result = export_document("测试文档", content, "html")
    if result.get("success"):
        print(f"✅ 成功: {result.get('file_name')}")
        print(f"   URL: {result.get('file_url')}")
    else:
        print(f"❌ 失败")
        return False

    return True


def test_engine_availability():
    """测试引擎可用性"""
    print("\n" + "=" * 60)
    print("测试 3: 引擎可用性检查")
    print("=" * 60)

    # Check PyMuPDF
    print("\n[1/3] 检查 PyMuPDF...")
    try:
        import fitz

        print(
            f"✅ PyMuPDF 已安装: {fitz.__version__ if hasattr(fitz, '__version__') else 'unknown'}"
        )
    except ImportError:
        print("⚠️  PyMuPDF 未安装 (pip install PyMuPDF)")

    # Check LibreOffice
    print("\n[2/3] 检查 LibreOffice...")
    import subprocess

    try:
        result = subprocess.run(
            ["soffice", "--version"], capture_output=True, timeout=5, check=False
        )
        if result.returncode == 0:
            version = result.stdout.decode().strip()
            print(f"✅ LibreOffice 已安装: {version}")
        else:
            print("⚠️  LibreOffice 未安装或不在 PATH")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print("⚠️  LibreOffice 未安装或不在 PATH")

    # Check python-docx
    print("\n[3/3] 检查 python-docx...")
    try:
        import docx

        print(f"✅ python-docx 已安装")
    except ImportError:
        print("⚠️  python-docx 未安装 (pip install python-docx)")

    return True


def main():
    print("\n" + "=" * 60)
    print("Format Export MCP - 集成测试")
    print("=" * 60)

    all_passed = True

    # Test 1: Markdown conversion
    try:
        if not test_markdown_conversion():
            all_passed = False
    except Exception as e:
        print(f"\n❌ 测试 1 异常: {e}")
        import traceback

        traceback.print_exc()
        all_passed = False

    # Test 2: Export document
    try:
        if not test_export_document():
            all_passed = False
    except Exception as e:
        print(f"\n❌ 测试 2 异常: {e}")
        import traceback

        traceback.print_exc()
        all_passed = False

    # Test 3: Engine availability
    try:
        test_engine_availability()
    except Exception as e:
        print(f"\n❌ 测试 3 异常: {e}")
        import traceback

        traceback.print_exc()

    # Summary
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ 所有测试通过！")
    else:
        print("❌ 部分测试失败")
    print("=" * 60)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
