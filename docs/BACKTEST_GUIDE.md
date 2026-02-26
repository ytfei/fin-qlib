# 📊 回测工具使用指南

## 功能特性

- ✅ 支持多种策略（TopkDropout、Topk）
- ✅ 自动风险分析
- ✅ 生成详细报告
- ✅ 可视化图表
- ✅ 灵活的配置选项

## 快速开始

### 1. 基础回测

```bash
# 使用默认参数
python -m fqlib.run_backtest

# 或使用快捷脚本
python scripts/run_backtest.py
```

默认参数：
- 持仓数量 (topk): 30
- 调仓卖出数量 (n_drop): 3
- 策略类型: TopkDropout

### 2. 自定义参数回测

```bash
# 持仓 50 只股票，每次调仓卖出 5 只
python -m fqlib.run_backtest --topk 50 --n-drop 5

# 指定日期范围
python -m fqlib.run_backtest --start 2025-01-01 --end 2025-06-30

# 使用 Topk 策略
python -m fqlib.run_backtest --strategy-type topk
```

### 3. 使用配置文件

创建配置文件 `my_backtest.yaml`：

```yaml
strategy:
  type: topk_dropout
  topk: 50
  n_drop: 5

date_range:
  start: 2025-01-01
  end: 2025-06-30

exchange:
  code: SH

output:
  dir: data/my_backtest
  generate_plots: true

manager:
  config_path: config/online_config.yaml
```

运行回测：

```bash
python -m fqlib.run_backtest --config my_backtest.yaml
```

---

## 📋 参数说明

### 策略参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--topk` | 持仓股票数量 | 30 |
| `--n-drop` | 调仓时卖出数量 | 3 |
| `--strategy-type` | 策略类型 | topk_dropout |

**策略类型**：
- `topk_dropout`: 每次持仓 topk 只，调仓时卖出 n_drop 只表现最差的
- `topk`: 持仓 topk 只，不主动卖出（等同于 n_drop=0）
- `soft_topk`: 软约束的 Topk 策略

### 日期参数

| 参数 | 说明 | 格式 |
|------|------|------|
| `--start` | 回测开始日期 | YYYY-MM-DD |
| `--end` | 回测结束日期 | YYYY-MM-DD |

如果不指定，则使用全部可用数据的日期范围。

### 输出参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--output-dir` | 输出目录 | data/backtest |
| `--no-save` | 不保存结果 | False |
| `--no-plots` | 不生成图表 | False |

---

## 📂 输出文件结构

运行回测后，会在输出目录生成以下文件：

```
data/backtest/20250226_123456/
├── report.csv              # 回测报告（每日收益）
├── positions.csv           # 每日持仓详情
├── analysis.yaml           # 风险分析指标
├── config.yaml             # 使用的配置
├── cumulative_return.png   # 累计收益曲线图
└── drawdown.png            # 回撤曲线图
```

### report.csv 说明

| 列名 | 说明 |
|------|------|
| date | 日期 |
| return | 策略当日收益率 |
| bench | 基准当日收益率 |

### analysis.yaml 说明

```yaml
# 收益指标
total_return: 0.15              # 总收益率
annualized_return: 0.12         # 年化收益率
bench_return: 0.08              # 基准收益
excess_return: 0.07             # 超额收益

# 风险指标
max_drawdown: -0.12             # 最大回撤
volatility: 0.15                # 波动率

# 风险调整收益
sharpe: 0.8                     # 夏普比率
information_ratio: 0.65         # 信息比率
calmar: 1.0                     # 卡玛比率
```

---

## 📈 回测报告示例

```
================================================================================
回测分析报告
================================================================================

📊 收益指标:
  总收益率: 15.23%
  基准收益: 8.45%
  超额收益: 6.78%

⚠️  风险指标:
  年化收益: 12.15%
  最大回撤: -12.34%
  波动率: 18.56%

📈 风险调整收益:
  夏普比率: 0.6543
  信息比率: 0.3652
  卡玛比率: 0.9846

================================================================================
```

---

## 🔧 高级用法

### 1. Python 代码调用

```python
from fqlib.run_backtest import run_backtest, BacktestConfig, print_analysis
from fqlib import ManagedOnlineManager

# 初始化 Manager
manager = ManagedOnlineManager("config/online_config.yaml")

# 创建配置
config = BacktestConfig(
    topk=50,
    n_drop=5,
    start_date="2025-01-01",
    end_date="2025-06-30",
    output_dir="data/my_backtest"
)

# 执行回测
report, positions, analysis = run_backtest(manager, config)

# 打印分析
print_analysis(analysis)
```

### 2. 批量回测

```python
# 测试不同的 topk 和 n_drop 组合
topk_list = [20, 30, 50]
n_drop_list = [3, 5, 10]

results = []

for topk in topk_list:
    for n_drop in n_drop_list:
        config = BacktestConfig(
            topk=topk,
            n_drop=n_drop,
            start_date="2025-01-01",
            end_date="2025-06-30"
        )

        report, positions, analysis = run_backtest(manager, config)

        results.append({
            'topk': topk,
            'n_drop': n_drop,
            'total_return': analysis.get('total_return'),
            'sharpe': analysis.get('sharpe'),
            'max_drawdown': analysis.get('max_drawdown')
        })

# 比较结果
import pandas as pd
results_df = pd.DataFrame(results)
print(results_df.sort_values('sharpe', ascending=False))
```

### 3. 自定义策略

```python
from qlib.contrib.strategy import BaseStrategy

class MyCustomStrategy(BaseStrategy):
    def __init__(self, signal, **kwargs):
        super().__init__(signal, **kwargs)

    def generate_order_list(self, scores):
        # 自定义交易逻辑
        # 返回订单列表
        pass

# 在回测中使用
strategy = MyCustomStrategy(signal=signals_df)
```

---

## ⚠️ 注意事项

### 1. 数据准备

回测前需要确保：
- ✅ 已完成模型训练
- ✅ 已生成预测信号
- ✅ 信号数据覆盖回测期间

检查可用日期：

```bash
python scripts/prediction_api_client.py dates
```

### 2. 日期选择

- 回测开始日期应该在信号范围内
- 建议预留至少 1 个月的预热期
- 回测结束日期不超过最新信号日期

### 3. 性能考虑

- 回测期间越长，执行时间越长
- 建议：
  - 初次测试：使用 3-6 个月数据
  - 正式回测：使用 1 年以上数据
  - topk 越大，回测越慢

### 4. 风险指标解读

- **夏普比率** > 1: 优秀
- **夏普比率** > 0.5: 良好
- **最大回撤** < 15%: 可接受
- **卡玛比率** > 1: 风险调整后收益良好

---

## 🐛 常见问题

### Q1: 回测失败，提示"No signals available"

**原因**: 没有预测信号数据

**解决**:
```bash
# 检查信号
python scripts/prediction_api_client.py status

# 如果没有信号，先运行训练和预测
```

### Q2: 图表生成失败

**原因**: matplotlib 未安装

**解决**:
```bash
pip install matplotlib
```

或者禁用图表生成：
```bash
python -m fqlib.run_backtest --no-plots
```

### Q3: 回测速度很慢

**原因**: 数据量大或复杂度高

**解决**:
- 减少回测期间
- 减小 topk 值
- 使用更简单的策略

---

## 📞 技术支持

如有问题，请查看：
- 项目文档: `docs/`
- 配置示例: `config/backtest_config.yaml`
- 日志文件: `data/backtest/*/logs/`
