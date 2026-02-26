# API Client SDK 创建总结

## 创建的文件

### 1. 核心 SDK 模块
**文件：** `fqlib/api_client.py`

**功能：**
- `StockPredictionClient` 类 - API 客户端
- 自动重试机制
- 错误处理（HTTPError, ConnectionError, TimeoutError）
- Context Manager 支持
- 类型提示
- 便捷方法（`get_top_predictions`, `get_prediction_summary`）

**主要方法：**
| 方法 | 说明 |
|------|------|
| `is_healthy()` | 快速健康检查 |
| `health()` | 详细健康状态 |
| `get_status()` | 服务状态 |
| `get_available_dates()` | 获取可用日期 |
| `get_predictions(date, top_n)` | 获取预测 |
| `batch_get_predictions(start, end, top_n)` | 批量查询 |
| `get_top_predictions(date, n)` | Top N 预测 |
| `get_prediction_summary(date)` | 汇总统计 |
| `close()` | 关闭连接 |

### 2. 重构的测试脚本
**文件：** `scripts/test_api_client.py`

**改进：**
- 使用新的 SDK
- 代码更简洁（从 274 行 → 285 行，但更清晰）
- 添加了汇总统计测试
- Context Manager 支持
- 更好的错误处理

**使用示例：**
```bash
# 基础测试
python scripts/test_api_client.py

# 自定义参数
python scripts/test_api_client.py --samples 10 --top-n 50

# 可重复测试
python scripts/test_api_client.py --seed 42
```

### 3. 文档

#### `docs/API_CLIENT_GUIDE.md`
完整的 SDK 使用指南，包含：
- 快速开始
- API 方法说明
- 错误处理
- 高级用法
- 完整示例
- 最佳实践

#### `docs/API_QUICKSTART.md` (更新)
添加了 Python SDK 使用章节，作为推荐的客户端方式

### 4. 模块导出更新
**文件：** `fqlib/__init__.py`

**添加：**
```python
from .api_client import StockPredictionClient

__all__ = [..., "StockPredictionClient"]
```

## SDK 特性

### 1. 简单易用

**之前（直接使用 requests）：**
```python
import requests

response = requests.get(
    "http://localhost:8000/predictions",
    params={"date": "2025-01-15", "top_n": 10},
    timeout=30
)
response.raise_for_status()
data = response.json()
```

**现在（使用 SDK）：**
```python
from fqlib import StockPredictionClient

client = StockPredictionClient()
data = client.get_predictions("2025-01-15", top_n=10)
```

### 2. 自动重试

SDK 内置智能重试机制：
- 自动重试 429, 500, 502, 503, 504 错误
- 指数退避策略（backoff_factor=0.5）
- 最多重试 3 次

```python
client = StockPredictionClient(
    base_url="http://localhost:8000",
    retry_count=5  # 自定义重试次数
)
```

### 3. 清晰的异常

```python
from fqlib.api_client import HTTPError, ConnectionError, TimeoutError

try:
    result = client.get_predictions("2025-01-15")
except ConnectionError as e:
    print(f"无法连接到服务器: {e}")
except HTTPError as e:
    print(f"HTTP 错误: {e}")
except TimeoutError as e:
    print(f"请求超时: {e}")
```

### 4. Context Manager 支持

```python
# 自动清理资源
with StockPredictionClient() as client:
    result = client.get_predictions("2025-01-15")
    # 处理数据...
# 连接自动关闭
```

### 5. 便捷方法

```python
# 快速获取 Top N
top_10 = client.get_top_predictions("2025-01-15", n=10)

# 获取汇总统计
summary = client.get_prediction_summary("2025-01-15")
print(f"平均分: {summary['score_stats']['mean']:.6f}")

# 快速健康检查
from fqlib.api_client import quick_check

if quick_check("http://localhost:8000"):
    print("服务正常！")
```

## 使用示例

### 示例1：简单查询

```python
from fqlib import StockPredictionClient

with StockPredictionClient() as client:
    predictions = client.get_top_predictions("2025-01-15", n=10)

    for i, pred in enumerate(predictions, 1):
        print(f"{i}. {pred['instrument']}: {pred['score']:.6f}")
```

### 示例2：批量导出

```python
import csv
from fqlib import StockPredictionClient

def export_predictions(start, end, filename):
    with StockPredictionClient() as client:
        batch = client.batch_get_predictions(start, end, top_n=50)

        with open(filename, 'w') as f:
            writer = csv.writer(f)
            writer.writerow(['date', 'instrument', 'score'])

            for date_pred in batch['predictions']:
                for pred in date_pred['predictions']:
                    writer.writerow([
                        date_pred['date'],
                        pred['instrument'],
                        pred['score']
                    ])

        print(f"Exported {batch['total_dates']} dates to {filename}")

export_predictions("2025-01-01", "2025-01-31", "predictions.csv")
```

### 示例3：监控脚本

```python
import time
from fqlib.api_client import quick_check, create_client

def monitor():
    print("开始监控服务状态...")

    while True:
        try:
            if quick_check():
                print("✅ 服务正常")
            else:
                print("❌ 服务异常")
        except Exception as e:
            print(f"❌ 检查失败: {e}")

        time.sleep(60)  # 每分钟检查一次

if __name__ == "__main__":
    monitor()
```

## 对比：SDK vs 直接调用 API

| 特性 | 直接调用 | SDK |
|------|---------|-----|
| 代码行数 | 多 | 少 |
| 错误处理 | 手动 | 自动 |
| 重试机制 | 无 | 有 |
| 类型提示 | 无 | 有 |
| 资源清理 | 手动 | 自动（with） |
| 便捷方法 | 无 | 有 |

## 文件结构

```
fqlib/
├── __init__.py                  # 导出 StockPredictionClient
├── api_client.py                # SDK 核心模块 (新)
├── api_server.py                # FastAPI 服务器
├── api_models.py                # Pydantic 模型
└── prediction_service.py         # 预测服务

scripts/
└── test_api_client.py          # 重构的测试脚本 (更新)

docs/
├── API_CLIENT_GUIDE.md          # SDK 使用指南 (新)
├── API_QUICKSTART.md            # 快速开始 (更新)
├── API_SERVER.md                # API 服务器文档
└── API_USAGE.md                 # 详细使用指南
```

## 导入方式

### 方式1：从 fqlib 导入（推荐）

```python
from fqlib import StockPredictionClient

client = StockPredictionClient()
```

### 方式2：直接导入

```python
from fqlib.api_client import StockPredictionClient, HTTPError

client = StockPredictionClient()
```

### 方式3：使用快捷函数

```python
from fqlib.api_client import create_client, quick_check

client = create_client("http://localhost:8000")
is_healthy = quick_check("http://localhost:8000")
```

## 测试

运行重构后的测试脚本：

```bash
# 基础测试
python scripts/test_api_client.py

# 测试不同参数
python scripts/test_api_client.py --samples 10 --top-n 50

# 可重复测试
python scripts/test_api_client.py --seed 42
```

## 下一步

1. **扩展 SDK** - 添加更多便捷方法
2. **异步支持** - 创建 async 版本的客户端
3. **缓存** - 添加本地缓存功能
4. **WebSocket** - 添加实时数据流支持

## 总结

✅ **创建了完整的 SDK** - 单文件模块，易于使用
✅ **重构了测试脚本** - 更简洁、更清晰
✅ **完善了文档** - 使用指南 + 示例
✅ **类型安全** - 完整的类型提示
✅ **生产就绪** - 重试、错误处理、资源管理
