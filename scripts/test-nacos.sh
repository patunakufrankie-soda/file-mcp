#!/bin/bash
# Nacos 本地测试脚本

set -e

echo "=== Nacos 集成测试 ==="

# 检查 Nacos 是否运行
if ! curl -s http://localhost:8848/nacos/v1/console/health/readiness > /dev/null; then
    echo "❌ Nacos 未运行，请先启动 Nacos"
    echo "   docker run -d -p 8848:8848 -p 9848:9848 --name nacos nacos/nacos-server:latest"
    exit 1
fi

echo "✅ Nacos 运行中"

# 上传配置到 Nacos
echo ""
echo "📤 上传配置到 Nacos..."

curl -X POST "http://localhost:8848/nacos/v1/cs/configs" \
  -d "dataId=format-export-mcp.yaml" \
  -d "group=DEFAULT_GROUP" \
  -d "content=$(cat nacos-config-example.yaml)"

echo ""
echo "✅ 配置上传成功"

# 设置环境变量
export NACOS_ENABLED=true
export NACOS_ENABLE_CONFIG=true
export NACOS_ENABLE_DISCOVERY=true
export NACOS_ENABLE_HOT_RELOAD=true
export NACOS_SERVER_ADDRESSES=localhost:8848
export NACOS_USERNAME=nacos
export NACOS_PASSWORD=nacos
export FORMAT_EXPORT_PORT=8000

echo ""
echo "📋 环境变量:"
echo "   NACOS_ENABLED=$NACOS_ENABLED"
echo "   NACOS_ENABLE_CONFIG=$NACOS_ENABLE_CONFIG"
echo "   NACOS_ENABLE_DISCOVERY=$NACOS_ENABLE_DISCOVERY"
echo "   FORMAT_EXPORT_PORT=$FORMAT_EXPORT_PORT"

echo ""
echo "🚀 启动服务..."
echo "   执行: format-export-http"
echo ""

# 启动服务（需要用户手动执行）
echo "请手动执行以下命令启动服务："
echo ""
echo "export NACOS_ENABLED=true"
echo "export NACOS_ENABLE_CONFIG=true"
echo "export NACOS_ENABLE_DISCOVERY=true"
echo "export NACOS_ENABLE_HOT_RELOAD=true"
echo "export NACOS_SERVER_ADDRESSES=localhost:8848"
echo "export NACOS_USERNAME=nacos"
echo "export NACOS_PASSWORD=nacos"
echo "python3 -m format_export_mcp.server_streamable_http"
echo ""
echo "然后访问 Nacos 控制台查看服务注册: http://localhost:8848/nacos"
