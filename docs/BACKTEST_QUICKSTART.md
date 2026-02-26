# 🚀 回测工具快速开始

## 基础使用

```bash
# 1. 使用默认参数运行回测
python -m fqlib.run_backtest

# 或使用快捷脚本
python scripts/run_backtest.py
```

## 常用参数

```bash
# 持仓 50 只，每次调仓卖出 5 只
python -m fqlib.run_backtest --topk 50 --n-drop 5

# 指定日期范围
python -m fqlib.run_backtest --start 2025-01-01 --end 2025-06-30

# 使用 Topk 策略（不主动卖出）
python -m fqlib.run_backtest --strategy-type topk

# 使用 Soft Topk 策略
python -m fqlib.run_backtest --strategy-type soft_topk

# 使用配置文件
python -m fqlib.run_backtest --config config/backtest_config.yaml
```

## 输出文件

运行后会在 `data/backtest/` 目录生成结果：

```
data/backtest/20250226_123456/
├── report.csv              # 每日收益
├── positions.csv           # 每日持仓
├── analysis.yaml           # 风险指标
├── config.yaml             # 配置
├── cumulative_return.png   # 收益曲线
└── drawdown.png            # 回撤曲线
```

## Python 代码调用

```python
from fqlib.run_backtest import run_backtest, BacktestConfig
from fqlib import ManagedOnlineManager

# 初始化
manager = ManagedOnlineManager("config/online_config.yaml")

# 配置
config = BacktestConfig(
    topk=30,
    n_drop=3,
    start_date="2025-01-01",
    end_date="2025-06-30"
)

# 执行回测
report, positions, analysis = run_backtest(manager, config)

# 查看结果
print(f"总收益: {analysis.get('total_return'):.2%}")
print(f"夏普比率: {analysis.get('sharpe'):.4f}")
print(f"最大回撤: {analysis.get('max_drawdown'):.2%}")
```

## 详细的回测指南

请查看：`docs/BACKTEST_GUIDE.md`
