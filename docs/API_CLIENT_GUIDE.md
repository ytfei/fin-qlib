# API Client SDK 使用指南

## 概述

`StockPredictionClient` 是一个简洁易用的 Python SDK，用于与股票预测回测 API 交互。

## 特性

- ✅ **简单易用** - 直观的方法签名和清晰的错误处理
- ✅ **类型提示** - 完整的类型注解，IDE 友好
- ✅ **重试机制** - 内置自动重试逻辑
- ✅ **Context Manager** - 支持 `with` 语句自动资源清理
- ✅ **便捷方法** - 内置常用操作的快捷方法

## 安装

SDK 已包含在 `fqlib` 包中，无需额外安装：

```python
from fqlib import StockPredictionClient
```

## 快速开始

### 基础用法

```python
from fqlib import StockPredictionClient

# 创建客户端
client = StockPredictionClient("http://localhost:8000")

# 健康检查
if client.is_healthy():
    print("Service is healthy!")

# 获取预测
result = client.get_predictions("2025-01-15", top_n=10)
print(f"Total predictions: {result['total_count']}")

# 关闭连接
client.close()
```

### 使用 Context Manager（推荐）

```python
from fqlib import StockPredictionClient

with StockPredictionClient("http://localhost:8000") as client:
    # 自动处理连接清理
    predictions = client.get_predictions("2025-01-15")
    print(predictions)
```

## API 方法

### 1. 健康检查

#### `is_healthy()` - 简单检查

```python
client = StockPredictionClient()

if client.is_healthy():
    print("✅ Service is up")
else:
    print("❌ Service is down")
```

#### `health()` - 详细状态

```python
health = client.health()

print(f"Status: {health['status']}")
print(f"Manager loaded: {health['manager_loaded']}")
print(f"Current time: {health.get('current_time')}")
print(f"Strategies: {health.get('strategies', [])}")
```

### 2. 获取状态

```python
status = client.get_status()

print(f"Service: {status['service_status']}")
print(f"Strategies: {status['manager']['n_strategies']}")

dates = status['available_dates']
print(f"Available dates: {dates['first']} to {dates['last']}")
print(f"Total dates: {dates['count']}")
```

### 3. 获取可用日期

```python
dates = client.get_available_dates()

print(f"Total dates: {len(dates)}")
print(f"First date: {dates[0]}")
print(f"Last date: {dates[-1]}")
```

### 4. 获取预测

#### 基础用法

```python
# 获取所有预测
result = client.get_predictions("2025-01-15")

print(f"Date: {result['date']}")
print(f"Total: {result['total_count']}")

for pred in result['predictions']:
    print(f"  {pred['instrument']}: {pred['score']:.6f}")
```

#### 获取 Top N

```python
# 只获取 Top 10
result = client.get_predictions("2025-01-15", top_n=10)

for pred in result['predictions']:
    print(f"{pred['instrument']}: {pred['score']:.6f} (rank: {pred['rank']})")
```

#### 便捷方法 - get_top_predictions

```python
# 直接获取 Top 10
top_10 = client.get_top_predictions("2025-01-15", n=10)

for i, pred in enumerate(top_10, 1):
    print(f"{i}. {pred['instrument']}: {pred['score']:.6f}")
```

### 5. 批量查询

```python
# 查询一个日期范围
result = client.batch_get_predictions(
    start_date="2025-01-10",
    end_date="2025-01-15"
)

for date_pred in result['predictions']:
    date = date_pred['date']
    count = date_pred['total_count']
    print(f"{date}: {count} predictions")
```

#### 批量查询 Top N

```python
# 每个日期只获取 Top 20
result = client.batch_get_predictions(
    start_date="2025-01-10",
    end_date="2025-01-15",
    top_n=20
)
```

### 6. 汇总统计

```python
summary = client.get_prediction_summary("2025-01-15")

print(f"Date: {summary['date']}")
print(f"Total predictions: {summary['total_count']}")

# 分数统计
stats = summary['score_stats']
print(f"Mean score: {stats['mean']:.6f}")
print(f"Std deviation: {stats['std']:.6f}")
print(f"Min score: {stats['min']:.6f}")
print(f"Max score: {stats['max']:.6f}")

# Top 10
print("\nTop 10:")
for pred in summary['top_10']:
    print(f"  {pred['instrument']}: {pred['score']:.6f}")
```

## 错误处理

SDK 定义了清晰的异常类型：

```python
from fqlib.api_client import (
    StockPredictionClient,
    HTTPError,
    ConnectionError,
    TimeoutError
)

client = StockPredictionClient()

try:
    result = client.get_predictions("2025-01-15")
except ConnectionError as e:
    print(f"Cannot connect to server: {e}")
except HTTPError as e:
    print(f"HTTP error: {e}")
except TimeoutError as e:
    print(f"Request timeout: {e}")
```

## 高级用法

### 自定义超时和重试

```python
# 创建客户端时自定义参数
client = StockPredictionClient(
    base_url="http://localhost:8000",
    timeout=60,           # 60秒超时
    retry_count=5        # 失败重试5次
)

result = client.get_predictions("2025-01-15")
```

### 快捷函数

```python
from fqlib.api_client import create_client, quick_check

# 创建客户端
client = create_client("http://localhost:8000", timeout=60)

# 快速健康检查
if quick_check("http://localhost:8000"):
    print("Service is healthy!")
```

## 完整示例

### 示例1：每日检查脚本

```python
#!/usr/bin/env python
"""每日预测检查脚本"""

from fqlib import StockPredictionClient
from datetime import datetime

def check_daily_prediction():
    with StockPredictionClient() as client:
        # 获取最新日期
        dates = client.get_available_dates()
        latest_date = dates[-1]

        print(f"Checking predictions for {latest_date}")

        # 获取汇总统计
        summary = client.get_prediction_summary(latest_date)

        print(f"\nTotal predictions: {summary['total_count']:,}")

        stats = summary['score_stats']
        print(f"Mean score: {stats['mean']:.6f}")
        print(f"Std: {stats['std']:.6f}")

        # Top 10
        print("\nTop 10 predictions:")
        for i, pred in enumerate(summary['top_10'], 1):
            print(f"  {i}. {pred['instrument']}: {pred['score']:.6f}")

if __name__ == "__main__":
    check_daily_prediction()
```

### 示例2：批量导出预测

```python
#!/usr/bin/env python
"""导出指定日期范围的预测"""

import csv
from fqlib import StockPredictionClient

def export_predictions(start_date, end_date, output_file):
    with StockPredictionClient() as client:
        result = client.batch_get_predictions(start_date, end_date)

        with open(output_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['date', 'instrument', 'score', 'rank'])

            for date_pred in result['predictions']:
                date = date_pred['date']
                for pred in date_pred['predictions']:
                    writer.writerow([
                        date,
                        pred['instrument'],
                        pred['score'],
                        pred.get('rank', '')
                    ])

        print(f"Exported {result['total_dates']} dates to {output_file}")

if __name__ == "__main__":
    export_predictions(
        "2025-01-01",
        "2025-01-31",
        "predictions.csv"
    )
```

### 示例3：监控脚本

```python
#!/usr/bin/env python
"""服务监控脚本"""

import time
from fqlib.api_client import quick_check, create_client

def monitor_service(interval=60):
    """每分钟检查服务健康状态"""
    print(f"Monitoring service (checking every {interval}s)...")

    while True:
        try:
            if quick_check():
                print("✅ Service healthy")
            else:
                print("❌ Service unhealthy!")
        except Exception as e:
            print(f"❌ Check failed: {e}")

        time.sleep(interval)

if __name__ == "__main__":
    try:
        monitor_service()
    except KeyboardInterrupt:
        print("\nStopped monitoring")
```

## 测试脚本使用

重构后的测试脚本现在使用 SDK：

```bash
# 基础测试
python scripts/test_api_client.py

# 自定义参数
python scripts/test_api_client.py --url http://localhost:8000 --samples 10 --top-n 50

# 使用随机种子（可重复）
python scripts/test_api_client.py --seed 42
```

## 最佳实践

1. **使用 Context Manager** - 确保资源正确清理
   ```python
   with StockPredictionClient() as client:
       # ... 代码 ...
   ```

2. **处理异常** - 捕获特定异常类型
   ```python
   try:
       result = client.get_predictions(date)
   except HTTPError as e:
       # 处理 HTTP 错误
       pass
   ```

3. **设置合理超时** - 根据网络环境调整
   ```python
   client = StockPredictionClient(timeout=60)
   ```

4. **使用批量查询** - 提高效率
   ```python
   # 好：一次获取多个日期
   client.batch_get_predictions(start, end)

   # 不好：多次单独查询
   for date in dates:
       client.get_predictions(date)
   ```

## API 参考

### StockPredictionClient

| 方法 | 说明 |
|------|------|
| `__init__(base_url, timeout, retry_count)` | 创建客户端实例 |
| `is_healthy()` | 快速健康检查 |
| `health()` | 详细健康状态 |
| `get_status()` | 服务状态信息 |
| `get_available_dates()` | 获取可用日期列表 |
| `get_predictions(date, top_n)` | 获取指定日期预测 |
| `batch_get_predictions(start, end, top_n)` | 批量获取预测 |
| `get_top_predictions(date, n)` | 获取 Top N 预测 |
| `get_prediction_summary(date)` | 获取汇总统计 |
| `close()` | 关闭连接 |

### 异常类型

| 异常 | 说明 |
|------|------|
| `HTTPError` | HTTP 错误（4xx, 5xx） |
| `ConnectionError` | 连接失败 |
| `TimeoutError` | 请求超时 |

## 相关文档

- [API Server 文档](API_SERVER.md)
- [API 使用指南](API_USAGE.md)
- [快速开始](API_QUICKSTART.md)
