# MLflow 集成 - 快速参考

## 🚀 5分钟上手

### 1. 安装依赖

```bash
pip install mlflow matplotlib seaborn scipy
```

### 2. 启动 MLflow UI（可选）

```bash
# 方式 1: 本地文件系统（默认）
# 无需启动，使用 ./mlruns 目录

# 方式 2: 启动 UI 服务器
mlflow ui --port 5000
# 访问 http://localhost:5000
```

### 3. 配置

复制配置文件：
```bash
cp config/online_config_mlflow.yaml config/my_mlflow_config.yaml
```

关键配置：
```yaml
online_manager:
  mlflow_integration:
    enabled: true  # 启用 MLflow
    experiment_name: "qlib_online"
    tracking_uri: null  # 或 "http://localhost:5000"

    auto_backtest:
      enabled: true
      top_n: 50
      lookback_days: 30
```

### 4. 运行

```bash
# 首次训练
python scripts/first_run_mlflow.py --config config/online_config_mlflow.yaml

# 日常更新
python scripts/run_routine_mlflow.py --config config/online_config_mlflow.yaml
```

### 5. 查看结果

打开 http://localhost:5000（如果启动了 UI）

---

## 📊 自动记录的内容

### 指标（Metrics）

| 类别 | 指标 |
|------|------|
| 训练 | `train_loss`, `valid_loss`, `train_time_seconds` |
| 预测 | `ic`, `rank_ic`, `n_predictions` |
| 回测 | `total_return`, `annual_return`, `sharpe_ratio`, `max_drawdown`, `win_rate` |

### 图表（Artifacts）

| 文件 | 说明 |
|------|------|
| `feature_importance.png` | 特征重要性柱状图 |
| `portfolio_returns.png` | 累计收益曲线 |
| `returns_distribution.png` | 收益分布直方图 |
| `feature_importance.csv` | 特征重要性数据 |
| `returns_data.csv` | 收益数据 |

---

## 🔄 在滚动训练中使用

### Crontab 配置

```bash
# 编辑 crontab
crontab -e

# 添加（每日收盘后运行）
30 16 * * 1-5 cd /path/to/fin-qlib && python scripts/run_routine_mlflow.py --config config/online_config_mlflow.yaml >> logs/routine_mlflow.log 2>&1
```

### 每次自动执行

```python
# 伪代码
每次 routine:
    1. 准备任务 (prepare_tasks)
    2. 训练模型 (train)
    3. 记录训练指标到 MLflow ✅
    4. 选择在线模型 (prepare_online_models)
    5. 记录预测指标 (IC, Rank IC) ✅
    6. 运行回测（最近 30 天）✅
    7. 记录回测指标和图表 ✅
    8. 生成信号 ✅
    9. 保存检查点 ✅
```

---

## 🎯 MLflow UI 使用指南

### 查看实验对比

1. 打开 http://localhost:5000
2. 选择实验: "qlib_online_production"
3. 查看 Runs 列表
4. 勾选多个 Runs
5. 点击 "Compare" 查看对比

### 关键操作

| 操作 | 说明 |
|------|------|
| **查看指标** | 点击 Run -> Metrics |
| **查看图表** | 点击 Run -> Artifacts |
| **对比 Runs** | 勾选多个 Runs -> Compare |
| **下载 Artifacts** | 点击文件名下载 |
| **复制 Run ID** | 点击 Run ID 旁边复制 |

---

## 💡 高级用法

### 1. 参数对比实验

```python
from fqlib.mlflow_integration import MLflowLogger

for lr in [0.01, 0.05, 0.1]:
    for depth in [6, 8, 10]:
        logger = MLflowLogger(experiment_name="param_tuning")
        logger.log_params({"lr": lr, "depth": depth})
        # 训练...
        logger.log_metrics({"ic": calculate_ic()})
        logger.end_run()

# 在 MLflow UI 中查看哪个参数组合最好
```

### 2. A/B 测试

```yaml
# 配置两个实验
strategies:
  - name: "Strategy_A"  # 原策略
    enabled: true

  - name: "Strategy_B"  # 新策略
    enabled: true

# 在 MLflow UI 中对比两个策略的 runs
```

### 3. 回溯历史

```python
# 查找特定日期的 run
from mlflow.tracking import MlflowClient

client = MlflowClient()
runs = client.search_runs(
    experiment_ids=["experiment_id"],
    filter_string="params.cur_time = '2024-01-15'"
)
```

---

## 📈 完整工作流程

```
┌─────────────────────────────────────────────────────────────┐
│                     训练流程                                  │
├─────────────────────────────────────────────────────────────┤
│  1. python scripts/first_run_mlflow.py                      │
│     └─> 创建 MLflow run                                      │
│     └─> 训练初始模型                                         │
│     └─> 记录训练指标 ✅                                      │
│     └─> 记录特征重要性 ✅                                    │
│     └─> 运行回测 ✅                                          │
│     └─> 结束 run                                             │
│     └─> 查看 http://localhost:5000                          │
├─────────────────────────────────────────────────────────────┤
│  2. python scripts/run_routine_mlflow.py (每日)             │
│     └─> 创建新的 MLflow run                                  │
│     └─> 检查是否需要重训练                                   │
│     └─> 如果需要:                                            │
│         ├─> 训练新模型                                        │
│         ├─> 记录训练指标 ✅                                   │
│         ├─> 记录预测指标 ✅                                   │
│         ├─> 述行回测 ✅                                       │
│         └─> 生成图表 ✅                                       │
│     └─> 结束 run                                             │
└─────────────────────────────────────────────────────────────┘

每次运行都会在 MLflow 中创建新的 run，包含：
- 完整的指标历史
- 可视化图表
- 训练参数
- 回测结果
```

---

## 🔧 配置选项

### 完整配置示例

```yaml
mlflow_integration:
  enabled: true
  experiment_name: "qlib_online_prod"
  tracking_uri: "http://localhost:5000"

  auto_backtest:
    enabled: true
    top_n: 50
    lookback_days: 30
    benchmark:
      enabled: true
      instrument: "SH000300"

  log_training_metrics: true
  log_feature_importance: true
  log_predictions: true
  log_plots: true
```

### 选项说明

| 选项 | 类型 | 说明 |
|------|------|------|
| `enabled` | bool | 是否启用 MLflow |
| `experiment_name` | str | 实验名称 |
| `tracking_uri` | str | MLflow 服务器地址 |
| `auto_backtest.enabled` | bool | 是否自动回测 |
| `auto_backtest.top_n` | int | 选择 Top N 股票 |
| `auto_backtest.lookback_days` | int | 回测窗口天数 |
| `auto_backtest.benchmark.enabled` | bool | 是否使用基准 |
| `log_training_metrics` | bool | 记录训练指标 |
| `log_feature_importance` | bool | 记录特征重要性 |
| `log_predictions` | bool | 记录预测指标 |
| `log_plots` | bool | 生成图表 |

---

## 🐛 常见问题

### Q: MLflow UI 无法访问

```bash
# 检查 MLflow 是否运行
ps aux | grep mlflow

# 或使用本地文件系统（无需启动）
tracking_uri: null
```

### Q: 图表不显示

```bash
# 安装依赖
pip install matplotlib seaborn

# 或关闭图表
log_plots: false
```

### Q: 指标为 NaN

已在代码中处理，会自动跳过 NaN 值。

---

## 📚 相关文档

- [完整指南](MLFLOW_GUIDE.md)
- [MLflow 官方文档](https://mlflow.org/docs/latest/)
- [项目主文档](../README.md)
