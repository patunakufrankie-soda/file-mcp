# Nacos 集成示例

## 环境变量配置

在启动服务前设置以下环境变量：

```bash
# 启用 Nacos
export NACOS_ENABLED=true

# Nacos 服务器地址
export NACOS_SERVER_ADDRESSES=localhost:8848

# 认证信息
export NACOS_USERNAME=nacos
export NACOS_PASSWORD=nacos

# 命名空间（可选）
export NACOS_NAMESPACE=public

# 启用功能
export NACOS_ENABLE_CONFIG=true        # 配置中心
export NACOS_ENABLE_DISCOVERY=true     # 服务注册
export NACOS_ENABLE_HOT_RELOAD=true    # 配置热更新

# 配置中心
export NACOS_DATA_ID=format-export-mcp.yaml
export NACOS_GROUP=DEFAULT_GROUP

# 服务注册（仅 HTTP/SSE 模式）
export NACOS_SERVICE_NAME=format-export-mcp
export NACOS_SERVICE_PORT=8000
export NACOS_CLUSTER_NAME=DEFAULT
```

## Nacos 配置上传

1. 登录 Nacos 控制台：http://localhost:8848/nacos

2. 进入 **配置管理** → **配置列表**

3. 点击 **+** 创建配置：
   - Data ID: `format-export-mcp.yaml`
   - Group: `DEFAULT_GROUP`
   - 配置格式: `YAML`
   - 配置内容: 复制 `nacos-config-example.yaml` 的内容

## 使用示例

### 1. HTTP 服务启动（支持服务注册）

```bash
# 设置环境变量
export NACOS_ENABLED=true
export NACOS_ENABLE_CONFIG=true
export NACOS_ENABLE_DISCOVERY=true
export NACOS_USERNAME=nacos
export NACOS_PASSWORD=nacos

# 启动服务
format-export-http
```

### 2. 在代码中使用配置

```python
from format_export_mcp.nacos.manager import NacosManager

# 获取配置
timeout = NacosManager.get_config("conversion.libreoffice.timeout", default=60)
max_pages = NacosManager.get_config("conversion.pdf.max_pages", default=500)
```

### 3. 配置热更新监听

```python
from format_export_mcp.nacos.manager import NacosManager

def on_config_change(config: dict):
    print(f"配置已更新: {config}")
    # 应用新配置...

client = NacosManager.get_client()
if client:
    client.add_config_listener(on_config_change)
```

## 功能说明

### 配置中心
- 集中管理转换引擎参数、超时时间、文件大小限制等
- 无需重启服务即可生效

### 服务注册与发现
- HTTP/SSE 模式自动注册到 Nacos
- 支持多实例负载均衡
- 自动心跳保活

### 配置热更新
- 监听 Nacos 配置变更
- 实时推送到服务实例
- 支持自定义监听器

## 注意事项

1. stdio 模式不支持服务注册（单进程本地通信）
2. 配置热更新需要业务代码主动监听并应用
3. 建议生产环境使用独立的 namespace 隔离配置
