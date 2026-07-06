# 🚀 快速部署指南（3分钟上手）

## 📦 部署到服务器的完整流程

### 方式 1: 自动配置（推荐）⭐

```bash
# 1. 运行配置向导
./configure.sh

# 按提示输入：
# - 文件服务器地址（必填）: http://your-server.com
# - 其他配置可直接回车使用默认值

# 2. 一键部署
./deploy.sh

# 3. 验证
curl http://localhost:8000/ready
```

---

### 方式 2: 手动配置

```bash
# 1. 修改配置文件
vim format_export_mcp/docker-compose.yml

# 修改以下配置：
# - FILE_SERVER_BASE_URL: http://your-server.com  # 必填！
# - 端口映射（如需要）
# - 存储目录

# 2. 创建存储目录
sudo mkdir -p /mnt/nfs/format-export/exports
sudo chown -R 1000:1000 /mnt/nfs/format-export/exports

# 3. 部署
cd format_export_mcp
docker-compose up -d --build

# 4. 查看日志
docker logs -f format-export-mcp
```

---

## 🔑 关键配置说明

### 必需配置 ⚠️

| 配置项 | 说明 | 示例 |
|--------|------|------|
| **FILE_SERVER_BASE_URL** | 内网文件服务器地址，用于拼接 `/api/file/` 路径 | `http://10.0.1.100:8080` |

**为什么需要 FILE_SERVER_BASE_URL？**

当你传入的 `input_uri` 是相对路径时（如 `/api/file/12345.txt`），系统会自动拼接：

```
输入: /api/file/12345.txt
拼接后: http://your-server.com/api/file/12345.txt
```

如果不配置此项，相对路径转换会报错：
```json
{
  "error_type": "validation_error",
  "message": "FILE_SERVER_BASE_URL environment variable is not set"
}
```

### 可选配置

- `FORMAT_EXPORT_IMAGE_SOURCE_BASE_URL`: 图片服务器（默认同 FILE_SERVER_BASE_URL）
- `FORMAT_EXPORT_FILE_TTL_SECONDS`: 文件过期时间（默认永久保留）
- 端口映射: 修改为其他端口避免冲突

---

## ✅ 部署验证

### 1. 检查服务状态

```bash
# 健康检查
curl http://localhost:8000/ready

# 支持的格式
curl http://localhost:8000/api/supported_conversions
```

### 2. 测试转换功能

#### 相对路径（自动拼接）

```bash
curl -X POST http://localhost:8000/api/convert_file_document \
  -H "Content-Type: application/json" \
  -d '{
    "input_uri": "/api/file/document.txt",
    "target_format": "pdf"
  }'
```

#### 完整 URL

```bash
curl -X POST http://localhost:8000/api/convert_file_document \
  -H "Content-Type: application/json" \
  -d '{
    "input_uri": "http://your-server.com/files/document.docx",
    "target_format": "pdf"
  }'
```

---

## 📂 关键文件说明

```text
file_mcp/
├── DEPLOYMENT.md
├── docs/
│   ├── ARCHITECTURE.md
│   ├── docker-deployment.md
│   └── frontend-integration.md
├── format_export_mcp/
│   ├── docker-compose.yml
│   ├── Dockerfile
│   ├── nginx.format-export.conf
│   └── README.md
├── tests/
└── pyproject.toml
```

---

## 🔧 常用命令

```bash
# 查看容器状态
docker ps | grep format-export-mcp

# 查看实时日志
docker logs -f format-export-mcp

# 重启服务
docker-compose restart

# 停止服务
docker-compose down

# 进入容器调试
docker exec -it format-export-mcp bash

# 更新服务
git pull
docker-compose up -d --build
```

---

## 🌐 配置 Nginx 反向代理（可选）

部署完成后，运行 `./configure.sh` 会自动生成 `nginx.conf.example`。

```bash
# 1. 复制配置
sudo cp nginx.conf.example /etc/nginx/sites-available/format-export

# 2. 启用站点
sudo ln -s /etc/nginx/sites-available/format-export /etc/nginx/sites-enabled/

# 3. 测试配置
sudo nginx -t

# 4. 重载 Nginx
sudo systemctl reload nginx
```

---

## ❓ 常见问题

### Q1: 相对路径转换报错

**错误**: `FILE_SERVER_BASE_URL environment variable is not set`

**解决**: 运行 `./configure.sh` 重新配置，或手动编辑 `docker-compose.yml` 添加 `FILE_SERVER_BASE_URL`

### Q2: 端口冲突

**错误**: `port is already allocated`

**解决**: 修改 `docker-compose.yml` 中的端口映射，如改为 `8001:8000`

### Q3: 文件下载 404

**解决**: 
1. 检查 Nginx 配置 `/downloads/` 路径
2. 确认存储目录权限正确

---

## 📞 支持文档

- **完整部署文档**: `DEPLOYMENT.md`
- **Docker 部署细节**: `docs/docker-deployment.md`
- **架构说明**: `docs/ARCHITECTURE.md`

---

## 🎯 三步部署总结

```bash
# 1️⃣ 配置
./configure.sh

# 2️⃣ 部署
./deploy.sh

# 3️⃣ 验证
curl http://localhost:8000/ready
```

**就是这么简单！** 🎉
