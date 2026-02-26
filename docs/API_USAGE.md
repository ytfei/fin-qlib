# 股票预测API使用指南

## 目录

1. [启动服务](#启动服务)
2. [使用客户端](#使用客户端)
3. [API接口说明](#api接口说明)
4. [常见问题](#常见问题)

---

## 启动服务

### 1. 前置条件

确保已满足以下条件：
- ✅ 已完成模型训练（生成了 `online_manager.pkl`）
- ✅ 配置文件 `config/online_config.yaml` 已正确配置
- ✅ 已安装依赖：`fastapi` 和 `uvicorn`

### 2. 安装依赖

```bash
# 如果还没安装依赖
uv sync

# 或者使用pip
pip install fastapi uvicorn
```

### 3. 启动API服务

#### 方式一：使用启动脚本（推荐）

```bash
python scripts/start_api_server.py
```

#### 方式二：使用uvicorn直接启动

```bash
uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
```

#### 方式三：配置环境变量启动

```bash
export CONFIG_PATH=config/online_config.yaml
export API_PORT=8080
python scripts/start_api_server.py
```

### 4. 验证服务启动

服务启动成功后，访问：
- API文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

```bash
# 使用curl测试
curl http://localhost:8000/health
```

---

## 使用客户端

我们提供了一个功能丰富的客户端脚本 `scripts/prediction_api_client.py`。

### 1. 查看服务状态

```bash
# 查看服务状态
python scripts/prediction_api_client.py status

# 输出示例：
# ================================================================================
#  服务状态
# ================================================================================
# 1️⃣  健康检查
#    状态: healthy
#    管理器已加载: 是
#    当前时间: 2025-01-10
#    策略数量: 1
```

### 2. 查看可用日期

```bash
# 查看所有可用日期
python scripts/prediction_api_client.py dates

# 查看最近10个日期
python scripts/prediction_api_client.py dates --limit 10
```

### 3. 查询指定日期的预测结果

```bash
# 查询2025-01-10的预测，显示Top 20
python scripts/prediction_api_client.py query --date 2025-01-10 --top 20 --display 20

# 查询并导出到CSV
python scripts/prediction_api_client.py query --date 2025-01-10 --output 2025-01-10_predictions.csv
```

输出示例：
```
================================================================================
 查询预测结果: 2025-01-10
================================================================================

📊 统计信息:
   日期: 2025-01-10
   总预测数: 5,000
   返回结果: 20

📊 2025-01-10 股票预测排行榜 (Top 20)
--------------------------------------------------------------------------------
排名    股票代码      预测得分      备注
--------------------------------------------------------------------------------
1     SH600000       0.023456    ⭐ 强烈推荐
2     SH600519       0.019876    ⭐ 强烈推荐
3     SZ000001       0.015432    ⭐ 强烈推荐
...
```

### 4. 查询特定股票

```bash
# 查询SH600000在2025-01-01到2025-01-10的预测
python scripts/prediction_api_client.py stock \
    --code SH600000 \
    --start 2025-01-01 \
    --end 2025-01-10
```

输出示例：
```
================================================================================
 股票预测查询: SH600000
================================================================================

📈 SH600000 预测历史
----------------------------------------------------
日期               预测得分        当日排名
----------------------------------------------------
2025-01-01       0.023456    1   📈
2025-01-02       0.019876    2   📈
2025-01-03      -0.005432    150 📉
...

📊 统计:
   平均得分: 0.012345
   最高得分: 0.023456
   最低得分: -0.005432
```

### 5. 批量导出

```bash
# 导出2025-01-01到2025-01-10的所有Top 10预测
python scripts/prediction_api_client.py export \
    --start 2025-01-01 \
    --end 2025-01-10 \
    --top 10 \
    --output predictions.csv
```

生成的CSV格式：
```csv
日期,排名,股票代码,预测得分
2025-01-01,1,SH600000,0.023456
2025-01-01,2,SH600519,0.019876
...
```

---

## API接口说明

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

### 2. 获取预测结果

```http
GET /predictions?date=2025-01-10&top_n=10
```

**查询参数：**
- `date`: 日期（必需）
- `top_n`: 返回Top N结果（可选）

**响应示例：**
```json
{
  "date": "2025-01-10",
  "predictions": [
    {"instrument": "SH600000", "score": 0.0234, "rank": 1},
    {"instrument": "SH600519", "score": 0.0198, "rank": 2}
  ],
  "total_count": 5000,
  "top_n": [...]
}
```

### 3. 批量获取预测

```http
GET /batch?start_date=2025-01-01&end_date=2025-01-10&top_n=5
```

### 4. 获取可用日期

```http
GET /dates
```

### 5. 获取服务状态

```http
GET /status
```

---

## 常见问题

### Q1: 服务启动失败，提示"Prediction service not available"

**原因：**
- 配置文件路径错误
- manager checkpoint不存在
- Qlib初始化失败

**解决方法：**
```bash
# 检查配置文件
ls -la config/online_config.yaml

# 检查checkpoint
ls -la data/checkpoints/online_manager.pkl

# 查看日志
tail -f data/logs/prediction_service_*.log
```

### Q2: 查询返回404错误

**原因：**
- 请求的日期没有预测数据

**解决方法：**
```bash
# 先查看可用日期
python scripts/prediction_api_client.py dates

# 使用可用日期查询
python scripts/prediction_api_client.py query --date 2025-01-10
```

### Q3: 如何添加自定义的股票池过滤？

修改客户端脚本，在查询结果后添加过滤逻辑：

```python
# 只返回沪深300成分股
csi300 = [...]  # 沪深300股票列表
filtered = [p for p in predictions if p['instrument'] in csi300]
```

### Q4: 如何在生产环境部署？

参考 `docs/API_SERVER.md` 中的部署章节：
- 使用多个worker进程
- 配置systemd服务
- 使用Docker容器化

### Q5: 如何设置API访问权限？

FastAPI支持多种认证方式，在 `api_server.py` 中添加：

```python
from fastapi.security import HTTPBearer

security = HTTPBearer()

@app.get("/predictions", dependencies=[Depends(security)])
async def get_predictions(...):
    ...
```

---

## 配置说明

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `CONFIG_PATH` | 配置文件路径 | `config/online_config.yaml` |
| `LOG_DIR` | 日志目录 | `data/logs` |
| `API_HOST` | 服务监听地址 | `0.0.0.0` |
| `API_PORT` | 服务监听端口 | `8000` |
| `API_WORKERS` | 工作进程数 | `1` |

### 配置文件 (config/online_config.yaml)

```yaml
online_manager:
  manager_path: "data/checkpoints/online_manager.pkl"

  signal_export:
    enabled: true
    dir: "data/signals"
    format: "csv"
    export_latest: true
    export_history: true  # 导出完整历史
```

---

## 高级用法

### 使用Python代码直接调用

```python
from fqlib.prediction_service import PredictionService

# 初始化服务
service = PredictionService("config/online_config.yaml")

# 获取预测
predictions = service.get_predictions("2025-01-10", top_n=10)

# 打印Top 10
for _, row in predictions.head(10).iterrows():
    print(f"{row['instrument']}: {row['score']}")
```

### 使用requests库调用API

```python
import requests

# 查询预测
response = requests.get(
    "http://localhost:8000/predictions",
    params={"date": "2025-01-10", "top_n": 10}
)
data = response.json()

# 处理结果
for pred in data['predictions']:
    print(f"{pred['instrument']}: {pred['score']}")
```

---

## 联系与支持

如有问题，请查看：
- 项目文档：`docs/`
- 日志文件：`data/logs/`
- GitHub Issues
