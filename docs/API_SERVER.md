# Stock Prediction Backtest API

FastAPI服务，用于获取股票预测结果。客户端只需传入日期，便可获得指定日期的预测结果。

## 功能特性

- 获取指定日期的股票预测结果
- 批量获取日期范围内的预测结果
- 查询可用的预测日期列表
- 自动集成已训练的Qlib模型
- 支持Top N股票筛选
- RESTful API设计
- 自动API文档生成

## 安装依赖

```bash
# 安装项目依赖
uv sync
```

## 启动服务

### 方式1: 使用Python脚本

```bash
python scripts/start_api_server.py
```

### 方式2: 使用uvicorn直接运行

```bash
uvicorn fqlib.api_server:app --host 0.0.0.0 --port 8000
```

### 环境变量配置

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `CONFIG_PATH` | 配置文件路径 | `config/online_config.yaml` |
| `LOG_DIR` | 日志目录 | `data/logs` |
| `API_HOST` | 服务器地址 | `0.0.0.0` |
| `API_PORT` | 服务器端口 | `8000` |
| `API_WORKERS` | 工作进程数 | `1` |

示例：
```bash
export CONFIG_PATH=config/online_config.yaml
export API_PORT=8080
python scripts/start_api_server.py
```

## API端点

### 1. 健康检查

```http
GET /health
```

**响应示例：**
```json
{
  "status": "healthy",
  "manager_loaded": true,
  "current_time": "2025-01-10",
  "strategies": ["LGB_Alpha158"]
}
```

### 2. 获取指定日期的预测结果

```http
GET /predictions?date=2025-01-10&top_n=10
```

**查询参数：**
- `date` (必需): 预测日期，格式 `YYYY-MM-DD`
- `top_n` (可选): 只返回前N个预测结果

**响应示例：**
```json
{
  "date": "2025-01-10",
  "predictions": [
    {
      "instrument": "SH600000",
      "score": 0.0234,
      "rank": 1
    },
    {
      "instrument": "SH600519",
      "score": 0.0198,
      "rank": 2
    }
  ],
  "total_count": 5000,
  "top_n": [
    {
      "instrument": "SH600000",
      "score": 0.0234,
      "rank": 1
    }
  ]
}
```

### 3. 批量获取日期范围内的预测结果

```http
GET /batch?start_date=2025-01-01&end_date=2025-01-10&top_n=5
```

**查询参数：**
- `start_date` (必需): 开始日期，格式 `YYYY-MM-DD`
- `end_date` (必需): 结束日期，格式 `YYYY-MM-DD`
- `top_n` (可选): 每个日期只返回前N个预测结果

**响应示例：**
```json
{
  "predictions": [
    {
      "date": "2025-01-01",
      "predictions": [
        {
          "instrument": "SH600000",
          "score": 0.0234,
          "rank": 1
        }
      ],
      "total_count": 5
    },
    {
      "date": "2025-01-02",
      "predictions": [
        {
          "instrument": "SH600519",
          "score": 0.0198,
          "rank": 1
        }
      ],
      "total_count": 5
    }
  ],
  "total_dates": 2
}
```

### 4. 获取可用日期列表

```http
GET /dates
```

**响应示例：**
```json
{
  "dates": [
    "2025-01-01",
    "2025-01-02",
    "2025-01-03"
  ],
  "count": 3
}
```

### 5. 获取服务状态

```http
GET /status
```

**响应示例：**
```json
{
  "service_status": "healthy",
  "prediction_service_loaded": true,
  "manager": {
    "n_strategies": 1,
    "strategies": ["LGB_Alpha158"],
    "cur_time": "2025-01-10",
    "signals_available": true,
    "signal_count": 5000
  },
  "available_dates": {
    "count": 10,
    "first": "2025-01-01",
    "last": "2025-01-10"
  }
}
```

## 使用示例

### Python客户端

使用提供的测试客户端：

```bash
python scripts/test_api_client.py --date 2025-01-10 --top-n 10
```

### 使用requests库

```python
import requests

# 获取指定日期的预测结果
response = requests.get(
    "http://localhost:8000/predictions",
    params={"date": "2025-01-10", "top_n": 10}
)
data = response.json()

# 打印前10个预测结果
for pred in data['top_n']:
    print(f"{pred['instrument']}: {pred['score']}")
```

### 使用curl

```bash
# 获取指定日期的预测结果
curl "http://localhost:8000/predictions?date=2025-01-10&top_n=10"

# 获取可用日期列表
curl "http://localhost:8000/dates"

# 批量获取预测结果
curl "http://localhost:8000/batch?start_date=2025-01-01&end_date=2025-01-10&top_n=5"
```

## API文档

服务启动后，访问以下地址查看交互式API文档：

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 文件结构

```
.
├── fqlib/
│   ├── api_server.py          # FastAPI服务器
│   ├── prediction_service.py  # 预测服务核心逻辑
│   ├── api_models.py          # API请求/响应模型
│   └── managed_manager.py     # 在线管理器
├── scripts/
│   ├── start_api_server.py    # 启动脚本
│   ├── test_api_client.py     # 随机测试脚本
│   └── prediction_api_client.py  # 完整功能客户端
└── config/
    └── online_config.yaml     # 配置文件
```

## 注意事项

1. **确保模型已训练**: 启动服务前，确保已经训练了模型并生成了信号文件
2. **配置文件路径**: 确保 `config/online_config.yaml` 配置正确
3. **数据文件**: 服务会自动加载 `data/checkpoints/online_manager.pkl`
4. **内存使用**: 大规模数据集可能需要较多内存，建议配置足够的资源

## 错误处理

API使用标准HTTP状态码：

- `200 OK`: 请求成功
- `400 Bad Request`: 请求参数错误
- `404 Not Found`: 请求的日期没有预测结果
- `500 Internal Server Error`: 服务器内部错误
- `503 Service Unavailable`: 预测服务未加载

错误响应示例：
```json
{
  "error": "ValidationError",
  "message": "No predictions available for date: 2025-01-10"
}
```

## 生产环境部署

### 使用多个worker进程

```bash
export API_WORKERS=4
python scripts/start_api_server.py
```

### 使用systemd服务

创建 `/etc/systemd/system/fin-qlib-api.service`:

```ini
[Unit]
Description=Stock Prediction Backtest API
After=network.target

[Service]
Type=notify
User=www-data
WorkingDirectory=/path/to/fin-qlib
Environment="CONFIG_PATH=config/online_config.yaml"
Environment="API_PORT=8000"
Environment="API_WORKERS=4"
ExecStart=/path/to/.venv/bin/python scripts/start_api_server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

启动服务：
```bash
sudo systemctl enable fin-qlib-api
sudo systemctl start fin-qlib-api
```

### 使用Docker

```dockerfile
FROM python:3.13-slim
WORKDIR /app
COPY . .
RUN pip install -e .
EXPOSE 8000
CMD ["python", "scripts/start_api_server.py"]
```

构建并运行：
```bash
docker build -t fin-qlib-api .
docker run -p 8000:8000 -v $(pwd)/data:/app/data fin-qlib-api
```

## 许可证

MIT License
