# 📅 预测信号时间逻辑说明

## 预测信号的时间含义

### 核心概念

在量化交易中，预测信号遵循以下时间逻辑：

```
T-1日数据（收盘后） → 模型预测 → T日信号 → T日交易
```

### 具体例子

假设今天是 **2025-08-19 上午 09:00**

| 时间点 | 可用数据 | 可获取的信号 | 说明 |
|--------|---------|------------|------|
| 2025-08-18 15:00 | 2025-08-18及之前 | **2025-08-19** | 用8/18数据预测8/19表现 |
| 2025-08-19 09:00 | 2025-08-18及之前 | **2025-08-19** | 还没有8/19收盘数据 |
| 2025-08-19 15:00 | 2025-08-19及之前 | **2025-08-20** | 8/19收盘后才生成 |

## ⚠️ 关键点

1. **信号日期 = 预测目标日期**
   - 信号标记为 `2025-08-19` 表示这是对8月19日股票表现的预测
   - 该信号通常在8月18日收盘后生成

2. **提前一天生成**
   - 8月19日的预测信号，在8月18日晚上就可用
   - 8月19日上午开盘前，使用这个信号进行交易决策

3. **上午09:00的使用场景**
   - 此时没有当日（8/19）的收盘数据
   - 应该使用前一天（8/18）生成的、目标日期为8/19的信号

## 📝 API调用指南

### 场景1：上午09:00获取当日预测

```python
import requests
from datetime import datetime

# 假设今天是 2025-08-19 上午 09:00
today = "2025-08-19"

# 获取对今天（8/19）的预测
# 这个预测是在昨天（8/18）晚上生成的
response = requests.get(
    "http://localhost:8000/predictions",
    params={"date": today, "top_n": 20}
)

data = response.json()

# 这些预测是基于8月18日及之前的数据生成的
# 用于指导8月19日的交易
print(f"📊 {today} 预测结果（基于8/18数据）:")
for pred in data['top_n']:
    print(f"  {pred['instrument']}: {pred['score']:.6f}")
```

### 场景2：获取可用的最新预测

```python
# 1. 先获取可用日期列表
response = requests.get("http://localhost:8000/dates")
dates = response.json()['dates']

# 2. 获取最新日期的预测
latest_date = dates[-1]
print(f"最新可用预测日期: {latest_date}")

# 3. 获取预测
response = requests.get(
    f"http://localhost:8000/predictions",
    params={"date": latest_date, "top_n": 20}
)
```

### 场景3：验证数据时效性

```python
def check_prediction_availability(target_date: str):
    """
    检查目标日期的预测是否可用

    Args:
        target_date: 目标交易日期，如 "2025-08-19"

    Returns:
        bool: 预测是否可用
    """
    from datetime import datetime, timedelta

    # 获取可用日期
    response = requests.get("http://localhost:8000/dates")
    available_dates = response.json()['dates']

    # 检查目标日期是否在可用列表中
    if target_date in available_dates:
        print(f"✅ {target_date} 的预测可用")
        print(f"   该预测基于前一日（{target_date}之前）的数据生成")
        return True
    else:
        print(f"❌ {target_date} 的预测不可用")
        if available_dates:
            print(f"   最新可用日期: {available_dates[-1]}")
        return False

# 使用示例
check_prediction_availability("2025-08-19")
```

## 🔄 工作流程图

```
┌─────────────────────────────────────────────────────────────┐
│  2025-08-18                                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 15:00 - 市场收盘                                   │   │
│  │    - 收集当日交易数据                             │   │
│  │    - 更新价格、成交量等                           │   │
│  └─────────────────────────────────────────────────────┘   │
│                        ↓                                     │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 18:00 - 数据处理完成                               │   │
│  │    - 数据清洗、特征工程                           │   │
│  │    - 准备模型输入                                 │   │
│  └─────────────────────────────────────────────────────┘   │
│                        ↓                                     │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 20:00 - 模型预测                                   │   │
│  │    - 运行模型                                     │   │
│  │    - 生成2025-08-19的预测信号                    │   │
│  │    - 信号可用！                                   │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│  2025-08-19                                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 09:00 - 开盘前                                     │   │
│  │    - 调用API获取2025-08-19的预测 ✅              │   │
│  │    - 根据预测进行交易决策                         │   │
│  │    - 下单交易                                     │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## 💡 实用建议

### 1. 自动化脚本 - 每日定时获取

```python
# scripts/daily_fetch_prediction.py
import requests
from datetime import datetime, timedelta

def fetch_todays_prediction():
    """获取今日的预测信号"""
    today = datetime.now().strftime("%Y-%m-%d")

    # 获取今日预测
    response = requests.get(
        "http://localhost:8000/predictions",
        params={"date": today, "top_n": 20}
    )

    if response.status_code == 200:
        data = response.json()

        print(f"📊 {today} 预测结果（Top 20）:")
        for i, pred in enumerate(data['top_n'], 1):
            print(f"{i:2}. {pred['instrument']}: {pred['score']:>10.6f}")

        return data
    else:
        print(f"❌ 获取预测失败: {response.status_code}")
        return None

if __name__ == "__main__":
    fetch_todays_prediction()
```

### 2. 定时任务配置

使用 cron 或系统定时任务，在每天早上08:30自动获取预测：

```bash
# crontab -e
# 每天早上08:30获取预测
30 8 * * 1-5 cd /path/to/fin-qlib && python scripts/daily_fetch_prediction.py
```

### 3. 检查数据更新时间

```python
def check_last_update():
    """检查最后更新时间"""
    response = requests.get("http://localhost:8000/status")

    if response.status_code == 200:
        status = response.json()

        if status.get('service_status') == 'healthy':
            manager = status['manager']
            available = status['available_dates']

            print(f"服务状态: 健康 ✅")
            print(f"当前时间: {manager.get('cur_time')}")
            print(f"可用日期数: {available.get('count')}")
            print(f"最新日期: {available.get('last')}")

            # 计算最新预测的生成时间
            from datetime import datetime
            last_date = available.get('last')
            if last_date:
                last_dt = datetime.strptime(last_date, "%Y-%m-%d")
                predict_date = last_dt - timedelta(days=1)
                print(f"预测生成时间: {predict_date.strftime('%Y-%m-%d')} 晚")

check_last_update()
```

## ⚠️ 常见问题

### Q1: 上午09:00调用API，能获取到当天的预测吗？

**答**: 可以！只要前一天（晚上）已经运行了模型训练/预测流程。

### Q2: 如何确认预测是最新的？

**答**: 检查 `/dates` 接口，最新日期应该是今天或明天。

### Q3: 如果今天的数据还没有怎么办？

**答**: 使用最新可用日期的预测：
```python
dates = get_available_dates()
latest = max(dates)  # 最新可用日期
predictions = get_predictions(latest)
```

### Q4: 信号的生成频率是怎样的？

**答**: 取决于你的训练配置：
- **每日更新**: 每天晚上生成次日预测
- **滚动更新**: 按配置的滚动周期（如每30天）重新训练

## 📞 技术支持

如有疑问，请查看：
- API文档: http://localhost:8000/docs
- 配置文件: `config/online_config.yaml`
- 训练日志: `data/logs/`
