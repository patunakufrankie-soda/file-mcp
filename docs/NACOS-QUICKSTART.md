# Nacos 快速配置指南

## 配置文件服务器地址

前端传相对路径（如 `/api/file/xxx.pdf`），需要 Nacos 提供完整地址。

### 1. 上传配置到 Nacos

浏览器打开 http://localhost:8848/nacos（或你公司的 Nacos 地址）

**创建配置：**
- Data ID: `format-export-mcp.yaml`
- Group: `DEFAULT_GROUP`
- 配置格式: `YAML`
- 配置内容：
```yaml
file_server:
  base_url: "http://192.168.1.100:9000"  # 改成你公司文件服务器地址
```

### 2. 启动服务

```bash
# 必须环境变量
export NACOS_ENABLED=true
export NACOS_ENABLE_CONFIG=true
export NACOS_SERVER_ADDRESSES=localhost:8848  # 或公司 Nacos 地址
export NACOS_USERNAME=nacos
export NACOS_PASSWORD=nacos

# 可选：本地兜底（Nacos 挂了时用）
export FILE_SERVER_BASE_URL=http://192.168.1.100:9000

# 启动
python3 -m format_export_mcp.server_streamable_http
```

### 3. 测试

前端传：`/api/file/documents/test.pdf`

服务自动拼接：`http://192.168.1.100:9000/api/file/documents/test.pdf`

### 4. 热更新

修改 Nacos 配置后，服务自动生效，无需重启。

## 部署到公司服务器

服务器上只需：
1. 安装 Python 包：`pip install nacos-sdk-python PyYAML`
2. 设置环境变量指向公司 Nacos
3. 启动服务

**不需要在服务器上部署 Nacos**，只要能网络访问公司的 Nacos 即可。
