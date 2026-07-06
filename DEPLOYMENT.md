# 📦 文档转换工具 Docker 部署指南

## 📋 目录
- [快速开始](#快速开始)
- [环境配置](#环境配置)
- [部署步骤](#部署步骤)
- [验证部署](#验证部署)
- [常见问题](#常见问题)

---

## 🚀 快速开始

### 前置要求
- Docker >= 20.10
- Docker Compose >= 2.0
- 服务器至少 2GB 内存
- 磁盘空间 >= 10GB（用于存储转换文件）

---

## ⚙️ 环境配置

### 1. 修改 `docker-compose.yml` 配置

编辑 `format_export_mcp/docker-compose.yml`：

```yaml
services:
  format-export-mcp:
    build:
      context: ..
      dockerfile: format_export_mcp/Dockerfile
    image: format-export-mcp:latest
    container_name: format-export-mcp
    restart: unless-stopped
    ports:
      - "8000:8000"  # 可修改为其他端口，如 "8001:8000"
    environment:
      # 必需配置
      FORMAT_EXPORT_HOST: 0.0.0.0
      FORMAT_EXPORT_PORT: 8000
      FORMAT_EXPORT_STORAGE_DIR: /data/format-export/exports
      FORMAT_EXPORT_PUBLIC_BASE_URL: /downloads
      
      # 重要：配置内网文件服务器地址（用于相对路径拼接）
      FILE_SERVER_BASE_URL: https://your-internal-server.com
      
      # 可选：配置图片服务器地址
      FORMAT_EXPORT_IMAGE_SOURCE_BASE_URL: https://your-internal-server.com
      
      # 可选：文件保留时间（秒）
      FORMAT_EXPORT_FILE_TTL_SECONDS: 3600
    volumes:
      # 持久化存储：将转换后的文件存储在宿主机
      - /mnt/nfs/format-export/exports:/data/format-export/exports
```

**关键配置说明**：

| 环境变量 | 必需 | 说明 | 示例 |
|---------|------|------|------|
| `FILE_SERVER_BASE_URL` | ⚠️ 相对路径时必需 | 内网文件服务器地址，用于拼接 `/api/file/` 开头的路径 | `http://10.0.1.100:8080` |
| `FORMAT_EXPORT_STORAGE_DIR` | ✅ | 容器内存储目录 | `/data/format-export/exports` |
| `FORMAT_EXPORT_PUBLIC_BASE_URL` | ✅ | 下载链接前缀 | `/downloads` |
| `FORMAT_EXPORT_IMAGE_SOURCE_BASE_URL` | ❌ | Markdown 图片服务器地址 | 同 FILE_SERVER_BASE_URL |
| `FORMAT_EXPORT_FILE_TTL_SECONDS` | ❌ | 文件过期时间（秒），默认永久保留 | `3600` |

### 2. 创建存储目录

```bash
# 在服务器上创建持久化存储目录
sudo mkdir -p /mnt/nfs/format-export/exports
sudo chown -R 1000:1000 /mnt/nfs/format-export/exports
sudo chmod 755 /mnt/nfs/format-export/exports
```

---

## 🐳 部署步骤

### 方式 1: 使用 docker-compose（推荐）

```bash
# 1. 上传代码到服务器
scp -r /Users/frankiesoda/file_mcp user@server:/opt/

# 2. SSH 登录服务器
ssh user@server

# 3. 进入项目目录
cd /opt/file_mcp/format_export_mcp

# 4. 修改配置（重要！）
vim docker-compose.yml
# 修改 FILE_SERVER_BASE_URL 为你的实际地址

# 5. 构建并启动
docker-compose up -d --build

# 6. 查看日志
docker-compose logs -f
```

### 方式 2: 直接使用 Docker 命令

```bash
# 1. 构建镜像
cd /opt/file_mcp
docker build -f format_export_mcp/Dockerfile -t format-export-mcp:latest .

# 2. 运行容器
docker run -d \
  --name format-export-mcp \
  --restart unless-stopped \
  -p 8000:8000 \
  -e FORMAT_EXPORT_HOST=0.0.0.0 \
  -e FORMAT_EXPORT_PORT=8000 \
  -e FORMAT_EXPORT_STORAGE_DIR=/data/format-export/exports \
  -e FORMAT_EXPORT_PUBLIC_BASE_URL=/downloads \
  -e FILE_SERVER_BASE_URL=http://your-server.com \
  -v /mnt/nfs/format-export/exports:/data/format-export/exports \
  format-export-mcp:latest
```

### 方式 3: 使用打包好的镜像

```bash
# 1. 加载镜像（如果有 tar 包）
docker load < format-export-mcp-latest.tar

# 2. 运行（同方式2）
docker run -d \
  --name format-export-mcp \
  --restart unless-stopped \
  -p 8000:8000 \
  -e FILE_SERVER_BASE_URL=http://your-server.com \
  -v /mnt/nfs/format-export/exports:/data/format-export/exports \
  format-export-mcp:latest
```

---

## ✅ 验证部署

### 1. 检查容器状态

```bash
# 查看运行状态
docker ps | grep format-export-mcp

# 查看日志
docker logs format-export-mcp

# 实时日志
docker logs -f format-export-mcp
```

### 2. 健康检查

```bash
# 检查服务是否就绪
curl http://localhost:8000/ready

# 预期返回
{
  "status": "ok",
  "storage_dir": "/data/format-export/exports"
}
```

### 3. 查看支持的转换格式

```bash
curl http://localhost:8000/api/supported_conversions

# 预期返回
{
  "success": true,
  "formats": ["txt", "md", "pdf", "docx"],
  "conversions": {
    "txt": ["md", "pdf", "docx"],
    "md": ["txt", "pdf", "docx"],
    "pdf": ["txt", "md", "docx"],
    "docx": ["txt", "md", "pdf"]
  }
}
```

### 4. 测试文件转换

#### 测试 1: 本地文件转换

```bash
# 创建测试文件
echo "测试内容" > /tmp/test.txt

# 复制到容器内
docker cp /tmp/test.txt format-export-mcp:/tmp/test.txt

# 调用转换 API
curl -X POST http://localhost:8000/api/convert_file_document \
  -H "Content-Type: application/json" \
  -d '{
    "input_uri": "/tmp/test.txt",
    "target_format": "pdf"
  }'

# 预期返回
{
  "success": true,
  "input_uri": "/tmp/test.txt",
  "output_path": "/data/format-export/exports/test_xxx.pdf",
  "output_url": "/downloads/test_xxx.pdf",
  "source_format": "txt",
  "target_format": "pdf",
  "message": "转换成功"
}
```

#### 测试 2: 相对路径自动拼接（需配置 FILE_SERVER_BASE_URL）

```bash
curl -X POST http://localhost:8000/api/convert_file_document \
  -H "Content-Type: application/json" \
  -d '{
    "input_uri": "/api/file/12345.txt",
    "target_format": "pdf"
  }'

# input_uri 会自动拼接为：
# http://your-server.com/api/file/12345.txt
```

#### 测试 3: 完整 URL（无需拼接）

```bash
curl -X POST http://localhost:8000/api/convert_file_document \
  -H "Content-Type: application/json" \
  -d '{
    "input_uri": "http://your-server.com/files/document.docx",
    "target_format": "pdf"
  }'
```

---

## 🔧 常见问题

### 1. 相对路径报错：FILE_SERVER_BASE_URL 未设置

**错误信息**:
```json
{
  "success": false,
  "error_type": "validation_error",
  "message": "Relative file path detected but FILE_SERVER_BASE_URL environment variable is not set"
}
```

**解决方案**:
在 `docker-compose.yml` 中添加：
```yaml
environment:
  FILE_SERVER_BASE_URL: http://your-internal-server.com
```

然后重启容器：
```bash
docker-compose restart
```

### 2. 文件下载 404

**问题**: 转换成功但无法下载文件

**解决方案**:
1. 检查存储目录权限
2. 确认 Nginx 配置了 `/downloads` 路径代理

示例 Nginx 配置：
```nginx
location /downloads/ {
    alias /mnt/nfs/format-export/exports/;
    autoindex off;
}

location /api/ {
    proxy_pass http://localhost:8000/api/;
}
```

### 3. 内网地址无法访问

**问题**: 转换内网文件时报错 `download_failed`

**解决方案**:
代码已自动处理内网地址跳过代理。检查：
1. FILE_SERVER_BASE_URL 配置正确
2. 容器网络可以访问内网服务器
3. 防火墙允许访问

测试网络连通性：
```bash
docker exec format-export-mcp ping your-internal-server.com
docker exec format-export-mcp curl -I http://your-internal-server.com/api/file/test
```

### 4. 容器启动失败

```bash
# 查看详细错误日志
docker logs format-export-mcp

# 检查配置
docker exec format-export-mcp env | grep FORMAT_EXPORT

# 进入容器调试
docker exec -it format-export-mcp bash
```

### 5. 磁盘空间不足

**问题**: 转换文件堆积占用磁盘

**解决方案**:
设置文件过期时间（自动清理）：
```yaml
environment:
  FORMAT_EXPORT_FILE_TTL_SECONDS: 3600  # 1小时后自动删除
```

或手动清理：
```bash
# 清理 7 天前的文件
find /mnt/nfs/format-export/exports -mtime +7 -delete
```

---

## 🔄 更新和维护

### 更新服务

```bash
# 1. 拉取最新代码
cd /opt/file_mcp
git pull

# 2. 重新构建
docker-compose build

# 3. 重启服务（零停机）
docker-compose up -d
```

### 备份数据

```bash
# 备份转换文件
tar -czf format-export-backup-$(date +%Y%m%d).tar.gz \
  /mnt/nfs/format-export/exports
```

### 查看资源使用

```bash
# 查看容器资源占用
docker stats format-export-mcp

# 查看磁盘使用
du -sh /mnt/nfs/format-export/exports
```

---

## 📞 技术支持

- 架构说明: `docs/ARCHITECTURE.md`
- 测试目录: `tests/`
- 项目仓库: [内部地址]

**部署完成后建议**:
1. ✅ 配置监控告警（磁盘、内存、错误日志）
2. ✅ 设置日志轮转
3. ✅ 配置 Nginx 反向代理
4. ✅ 启用 HTTPS
5. ✅ 定期备份转换文件
