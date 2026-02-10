# MLflow 集成使用指南

本指南说明如何在滚动训练中集成 MLflow，自动记录：
- 模型训练指标
- 特征重要性
- 预测指标（IC, Rank IC）
- 回测结果和收益分析
- 可视化图表

---

## 📦 安装依赖

```bash
pip install mlflow matplotlib seaborn scipy
```

---

## 🚀 快速开始

### 步骤 1: 启动 MLflow 服务器（可选）

```bash
# 方式 1: 使用本地文件系统（默认）
# 无需启动服务器，MLflow 会使用 ./mlruns 目录

# 方式 2: 启动 MLflow UI 服务器
mlflow ui --port 5000

# 访问 http://localhost:5000 查看实验
```

### 步骤 2: 更新配置

编辑 `config/online_config_mlflow.yaml`:

```yaml
online_manager:
  # ... 其他配置

  # 启用 MLflow 集成
  mlflow_integration:
    enabled: true
    experiment_name: "qlib_online_production"
    tracking_uri: null  # 或 "http://localhost:5000"

    auto_backtest:
      enabled: true
      top_n: 50
      lookback_days: 30

    log_training_metrics: true
    log_feature_importance: true
    log_predictions: true
    log_plots: true
```

### 步骤 3: 运行训练

```bash
# 首次训练
python scripts/first_run_mlflow.py --config config/online_config_mlflow.yaml

# 日常更新（自动记录指标）
python scripts/run_routine_mlflow.py --config config/online_config_mlflow.yaml
```

### 步骤 4: 查看 MLflow UI

```bash
# 如果启动了 MLflow UI
# 访问 http://localhost:5000

# 查看实验
# - Experiments: qlib_online_production
# - Runs: 每次训练/runroutine 自动创建新的 run
# - Metrics: IC, Rank IC, 累计收益, 最大回撤等
# - Artifacts: 特征重要性图, 收益曲线图, 数据文件
```

---

## 📊 记录的指标

### 训练指标

| 指标 | 说明 |
|------|------|
| `train_loss` | 训练损失 |
| `valid_loss` | 验证损失 |
| `train_time_seconds` | 训练耗时 |
| `n_features` | 特征数量 |
| `n_estimators` | 树的数量 |
| `num_leaves` | 叶子节点数 |

### 预测指标

| 指标 | 说明 |
|------|------|
| `ic` | Information Coefficient（相关系数） |
| `rank_ic` | Rank IC（排名相关系数） |
| `ic_std` | IC 标准差 |
| `n_predictions` | 预测数量 |

### 回测指标

| 指标 | 说明 |
|------|------|
| `total_return` | 累计收益率 |
| `annual_return` | 年化收益率 |
| `volatility` | 波动率（年化） |
| `sharpe_ratio` | 夏普比率 |
| `max_drawdown` | 最大回撤 |
| `win_rate` | 胜率 |
| `excess_return` | 超额收益 |
| `information_ratio` | 信息比率 |
| `correlation_with_benchmark` | 与基准的相关系数 |

### Artifacts（文件）

| 文件 | 说明 |
|------|------|
| `feature_importance.csv` | 特征重要性数据 |
| `feature_importance.png` | 特征重要性图 |
| `portfolio_returns.png` | 组合收益曲线图 |
| `returns_distribution.png` | 收益分布图 |
| `returns_data.csv` | 收益数据 |

---

## 🔧 在滚动训练中使用

### 自动模式（推荐）

使用 `scripts/run_routine_mlflow.py`，会自动：
1. 训练模型
2. 记录训练指标
3. 更新在线模型
4. 运行回测
5. 记录回测结果和图表

```bash
# 设置定时任务
crontab -e

# 添加（每日收盘后运行）
30 16 * * 1-5 cd /path/to/fin-qlib && python scripts/run_routine_mlflow.py --config config/online_config_mlflow.yaml >> logs/routine_mlflow.log 2>&1
```

每次运行会：
- ✅ 记录训练指标
- ✅ 记录 IC/Rank IC
- ✅ 运行回测（最近 30 天）
- ✅ 生成图表
- ✅ 自动上传到 MLflow

---

## 💻 代码示例

### 示例 1: 手动使用 MLflow Logger

```python
from fqlib.mlflow_integration import (
    MLflowLogger,
    QlibMetricsLogger,
    QlibBacktestAnalyzer,
)

# 1. 创建 MLflow Logger
mlflow_logger = MLflowLogger(
    experiment_name="my_experiment",
    tracking_uri="http://localhost:5000"
)

# 2. 训练模型
model = train_model(...)
mlflow_logger.log_metrics({
    "train_loss": 0.123,
    "valid_loss": 0.145,
    "train_time": 120
})

# 3. 记录预测指标
metrics_logger = QlibMetricsLogger(mlflow_logger)
metrics_logger.log_prediction_metrics(predictions, labels)

# 4. 记录特征重要性
metrics_logger.log_feature_importance(model, feature_names, top_n=20)

# 5. 运行回测
analyzer = QlibBacktestAnalyzer(mlflow_logger)
analyzer.analyze_and_log(
    predictions=pred_df,
    returns=returns_df,
    benchmark_returns=benchmark_df,
    top_n=50
)

# 6. 结束 run
mlflow_logger.end_run()
```

### 示例 2: 包装现有策略

```python
from fqlib.mlflow_integration import MLflowEnabledStrategy
from qlib.workflow.online.strategy import RollingStrategy

# 原始策略
strategy = RollingStrategy(...)

# 包装为 MLflow 集成策略
mlflow_logger = MLflowLogger(experiment_name="my_strategy")
mlflow_strategy = MLflowEnabledStrategy(strategy, mlflow_logger)

# 使用方式完全相同
tasks = mlflow_strategy.prepare_tasks(cur_time)
models = trainer.train(tasks)
mlflow_strategy.prepare_online_models(models)  # 自动记录指标

# 运行回测
mlflow_strategy.run_backtest_and_log("2023-01-01", "2024-01-01")
```

### 示例 3: 批量实验对比

```python
from fqlib.mlflow_integration import MLflowLogger

# 对比不同参数
for learning_rate in [0.01, 0.05, 0.1]:
    for max_depth in [6, 8, 10]:
        # 开始新的 run
        logger = MLflowLogger(
            experiment_name="parameter_tuning"
        )
        logger.start_run()

        # 记录参数
        logger.log_params({
            "learning_rate": learning_rate,
            "max_depth": max_depth
        })

        # 训练
        model = train_model(lr=learning_rate, depth=max_depth)

        # 记录指标
        logger.log_metrics({
            "ic": calculate_ic(model),
            "sharpe": backtest(model)
        })

        # 结束
        logger.end_run()

# 在 MLflow UI 中对比结果
```

---

## 🎨 MLflow UI 使用

### 查看实验对比

```
1. 打开 http://localhost:5000

2. 选择实验: "qlib_online_production"

3. 查看 Runs 列表:
   - 每一行代表一次训练/routine
   - 可以看到每个 run 的关键指标

4. 点击具体的 Run:
   - Metrics: 指标随时间变化
   - Parameters: 超参数
   - Artifacts: 图表和数据文件

5. 对比多个 Runs:
   - 勾选多个 Runs
   - 点击 "Compare" 按钮
   - 查看指标对比表格
   - 查看并行的指标图表
```

### 导出结果

```bash
# 导出实验为 CSV
mlflow experiments export -i <experiment_id> -o experiment.csv

# 下载 artifacts
mlflow artifacts download -r <run_id>/artifacts -o ./artifacts
```

---

## 📈 高级用法

### 1. 条件记录

只在满足条件时记录：

```python
# 配置
mlflow_integration:
  enabled: true
  auto_backtest:
    enabled: true
    only_when_new_model: true  # 只在有新模型时回测

# 代码
if strategy.prepare_tasks(cur_time):  # 有新任务
    # 训练并记录
    ...
    mlflow_strategy.run_backtest_and_log(...)
```

### 2. 多实验管理

```python
# 开发环境
dev_logger = MLflowLogger(
    experiment_name="qlib_online_dev",
    tracking_uri="http://dev-server:5000"
)

# 生产环境
prod_logger = MLflowLogger(
    experiment_name="qlib_online_prod",
    tracking_uri="http://prod-server:5000"
)
```

### 3. 自定义指标

```python
# 在 mlflow_integration.py 中添加

def log_custom_metrics(self, predictions, returns):
    """自定义指标计算"""
    # 计算自定义指标
    custom_metric = calculate_your_metric(predictions, returns)

    # 记录
    self.logger.log_metrics({
        'custom_metric_1': custom_metric.value1,
        'custom_metric_2': custom_metric.value2,
    })

    # 生成自定义图表
    fig = plot_custom_chart(predictions)
    self.logger.log_figure(fig, 'custom_chart.png')
```

### 4. 告警集成

```python
# 集成告警（如 Slack, Email）

def check_and_alert(metrics):
    """检查指标并发送告警"""
    if metrics['sharpe_ratio'] < 0.5:
        send_alert(f"Low Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")

    if metrics['max_drawdown'] < -0.1:
        send_alert(f"High Drawdown: {metrics['max_drawdown']:.2f}")

# 在 routine 后调用
metrics = analyzer.analyze_and_log(...)
check_and_alert(metrics)
```

---

## 🔍 故障排查

### 问题 1: MLflow 连接失败

```
Error: Failed to connect to MLflow server
```

**解决**：
```bash
# 检查 MLflow 服务是否运行
mlflow ui

# 或使用本地文件系统（无需服务器）
tracking_uri: null
```

### 问题 2: 图表无法显示

```
Error: No module named 'matplotlib'
```

**解决**：
```bash
pip install matplotlib seaborn

# 或在代码中跳过图表
log_plots: false
```

### 问题 3: 指标为 NaN

**解决**：
```python
# 在 mlflow_integration.py 中已处理
# 使用 if not np.isnan(value) 检查

# 或手动过滤
metrics = {k: v for k, v in metrics.items() if not np.isnan(v)}
```

---

## 📚 相关文档

- [MLflow 官方文档](https://mlflow.org/docs/latest/index.html)
- [Qlib 回测分析](https://qlib.readthedocs.io/en/latest/component/backtest.html)
- [项目主文档](../README.md)

---

## 💡 最佳实践

1. **定期查看 MLflow UI**：了解模型性能趋势
2. **对比不同策略**：使用多个 experiments 分离不同策略
3. **设置告警**：关键指标异常时及时通知
4. **版本控制**：记录好每次实验的参数和结果
5. **定期清理**：删除旧的 runs 避免数据过大
