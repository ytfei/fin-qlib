# 🚀 快速开始

## 1. 启动API服务

### 方式一：使用启动脚本（最简单）

```bash
# Linux/Mac
chmod +x start_api.sh
./start_api.sh
```

### 方式二：使用Python脚本

```bash
python scripts/start_api_server.py
```

### 方式三：自定义端口启动

```bash
export API_PORT=8080
python scripts/start_api_server.py
```

服务启动后，访问 http://localhost:8000/docs 查看API文档。

---

## 2. 使用Python SDK（推荐）

### 安装

SDK 已包含在 `fqlib` 包中：

```python
from fqlib import StockPredictionClient
```

### 快速示例

```python
from fqlib import StockPredictionClient

# 创建客户端（支持 context manager）
with StockPredictionClient("http://localhost:8000") as client:

    # 健康检查
    if client.is_healthy():
        print("✅ Service is healthy")

    # 获取预测
    result = client.get_predictions("2025-01-15", top_n=10)

    print(f"Total predictions: {result['total_count']}")
    for pred in result['predictions']:
        print(f"  {pred['instrument']}: {pred['score']:.6f}")
```

### 更多功能

```python
# 获取可用日期
dates = client.get_available_dates()
print(f"Available dates: {dates[0]} to {dates[-1]}")

# 批量查询
batch = client.batch_get_predictions("2025-01-10", "2025-01-15")
for date_pred in batch['predictions']:
    print(f"{date_pred['date']}: {date_pred['total_count']} predictions")

# 汇总统计
summary = client.get_prediction_summary("2025-01-15")
print(f"Mean score: {summary['score_stats']['mean']:.6f}")
```

详细文档请查看 [API_CLIENT_GUIDE.md](API_CLIENT_GUIDE.md)

---

## 3. 使用命令行工具

### 查看服务状态

```bash
python scripts/prediction_api_client.py status
```

### 查看可用日期

```bash
python scripts/prediction_api_client.py dates
```

### 查询某日预测

```bash
# 查看2025-01-10的Top 20股票
python scripts/prediction_api_client.py query --date 2025-01-10 --top 20 --display 20
```

### 查询特定股票

```bash
# 查询SH600000的历史预测
python scripts/prediction_api_client.py stock \
    --code SH600000 \
    --start 2025-01-01 \
    --end 2025-01-10
```

### 批量导出

```bash
# 导出Top 10预测到CSV
python scripts/prediction_api_client.py export \
    --start 2025-01-01 \
    --end 2025-01-10 \
    --top 10 \
    --output predictions.csv
```

---

## 4. 测试API服务

### 随机测试（推荐）

```bash
# 随机测试5个日期的预测
python scripts/test_api_client.py

# 随机测试10个日期，每个日期显示Top 30
python scripts/test_api_client.py --samples 10 --top-n 30

# 使用固定随机种子（可重复测试）
python scripts/test_api_client.py --seed 42 --samples 5
```

测试输出示例：
```
================================================================================
 随机预测测试 (随机选择 5 个日期)
================================================================================

✅ 健康检查通过
   状态: healthy
   管理器已加载: True

--------------------------------------------------------------------------------
 服务状态
--------------------------------------------------------------------------------

策略数量: 1
策略: LGB_Alpha158
可用日期数: 10
日期范围: 2025-01-01 至 2025-01-10

--------------------------------------------------------------------------------
 获取可用日期
--------------------------------------------------------------------------------

总共有 10 个日期的预测数据

📅 随机选择 5 个日期进行测试:
   1. 2025-01-03
   2. 2025-01-07
   3. 2025-01-01
   4. 2025-01-09
   5. 2025-01-05

--------------------------------------------------------------------------------
 预测测试结果
--------------------------------------------------------------------------------

📊 测试日期 1/5: 2025-01-03
   ✅ 成功
   总预测数: 5,000
   返回结果: 20

   Top 5 预测:
      1. SH600000: 0.023456 (排名: 1)
      2. SH600519: 0.019876 (排名: 2)
      3. SZ000001: 0.015432 (排名: 3)
      ...

================================================================================
 测试总结
================================================================================

测试日期数: 5
成功: 5 ✅
失败: 0 ❌
成功率: 100.0%

🎉 所有测试通过！
```

---

## 5. API接口

### 使用curl

```bash
# 健康检查
curl http://localhost:8000/health

# 获取预测
curl "http://localhost:8000/predictions?date=2025-01-10&top_n=10"
```

### 使用Python

```python
import requests

# 获取预测
response = requests.get(
    "http://localhost:8000/predictions",
    params={"date": "2025-01-10", "top_n": 10}
)
data = response.json()

# 打印结果
for pred in data['predictions']:
    print(f"{pred['instrument']}: {pred['score']}")
```

---

## 6. 常见问题

### Q: 服务启动失败？
```bash
# 检查配置文件
ls config/online_config.yaml

# 检查checkpoint
ls data/checkpoints/online_manager.pkl
```

### Q: 没有预测数据？
```bash
# 先查看可用日期
python scripts/prediction_api_client.py dates
```

详细文档请查看 [API_USAGE.md](API_USAGE.md)
