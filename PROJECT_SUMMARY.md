# Fin-Qlib 项目总结

## 📦 项目概述

基于 Qlib 的生产级量化交易在线模型管理系统，支持：
- 配置驱动的多策略管理
- 滚动训练和模型动态切换
- 多种信号集成方法
- **MLflow 集成**（训练指标、回测分析、可视化）
- 自定义策略和因子
- Docker 部署

---

## 🎯 核心特性

### 1. 基础功能
- ✅ 配置驱动架构（YAML）
- ✅ 多策略管理（动态添加/删除）
- ✅ 滚动训练
- ✅ 信号导出（CSV/Parquet）
- ✅ 定时任务集成（Cron）

### 2. 高级功能
- ✅ 5种信号集成方法（Average, Weighted, Dynamic, Voting, Best）
- ✅ 自定义策略支持
- ✅ 自定义因子（Handler）支持
- ✅ 策略性能评估
- ✅ 热更新（无需重启）

### 3. MLflow 集成 ⭐
- ✅ 自动记录训练指标
- ✅ 自动记录预测指标（IC, Rank IC）
- ✅ 自动回测分析
- ✅ 特征重要性可视化
- ✅ 收益曲线可视化
- ✅ 实验对比和分析

---

## 📂 项目结构

```
fin-qlib/
├── 📚 文档 (12个文档文件)
│   ├── README.md                      # 主文档
│   ├── QUICKSTART.md                  # 快速开始
│   ├── PROJECT_STRUCTURE.md           # 架构说明
│   ├── docs/
│   │   ├── QUICK_REFERENCE.md         # 自定义策略快速参考
│   │   ├── CUSTOM_STRATEGY_GUIDE.md   # 自定义策略详细教程
│   │   ├── HOW_TO_ADD_CUSTOM.md       # 添加自定义指南
│   │   ├── MLFLOW_GUIDE.md            # MLflow 完整指南
│   │   └── MLFLOW_QUICKSTART.md       # MLflow 快速参考
│
├── 💡 示例代码 (2个文件)
│   └── examples/
│       ├── custom_handler_example.py  # 自定义 Handler 示例
│       └── custom_strategy_example.py # 自定义 Strategy 示例
│
├── 🔧 核心代码 (3个文件)
│   └── src/
│       ├── __init__.py
│       ├── managed_manager.py         # 配置驱动的 Manager
│       ├── ensemble.py                # 5种集成方法
│       └── mlflow_integration.py      # MLflow 集成 ⭐
│
├── ⚙️ 配置 (4个文件)
│   └── config/
│       ├── online_config_template.yaml   # 完整模板
│       ├── online_config_simple.yaml     # 简化配置
│       ├── online_config_custom.yaml     # 自定义示例
│       └── online_config_mlflow.yaml     # MLflow 配置 ⭐
│
├── 🚀 脚本 (8个文件)
│   └── scripts/
│       ├── test_config.py                # 配置验证
│       ├── first_run.py                  # 初始化
│       ├── run_routine.py                # 日常更新
│       ├── first_run_mlflow.py           # 初始化（带MLflow）⭐
│       ├── run_routine_mlflow.py         # 日常更新（带MLflow）⭐
│       ├── evaluate.py                   # 策略评估
│       ├── get_signals.py                # 导出信号
│       └── upgrade_strategy.py           # 策略管理
│
└── 🐳 部署
    ├── Dockerfile
    ├── docker-compose.yml               # 包含 MLflow+MongoDB
    ├── deploy.sh
    └── requirements.txt                 # 更新了 MLflow 依赖
```

---

## 🚀 使用指南

### 场景 1: 基础使用（无 MLflow）

```bash
# 1. 配置
cp config/online_config_simple.yaml config/online_config.yaml
# 编辑配置

# 2. 初始化
python scripts/first_run.py --config config/online_config.yaml

# 3. 日常更新
python scripts/run_routine.py --config config/online_config.yaml
```

### 场景 2: 使用 MLflow（推荐）⭐

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动 MLflow UI（可选）
mlflow ui --port 5000

# 3. 配置
cp config/online_config_mlflow.yaml config/my_config.yaml
# 编辑配置，确保 mlflow_integration.enabled = true

# 4. 初始化
python scripts/first_run_mlflow.py --config config/my_config.yaml

# 5. 日常更新（自动记录指标和图表）
python scripts/run_routine_mlflow.py --config config/my_config.yaml

# 6. 查看结果
# 打开 http://localhost:5000
```

### 场景 3: 添加自定义因子

```bash
# 1. 创建 Handler
mkdir -p my_handlers
# 编辑 my_handlers/my_factors.py（参考 docs/QUICK_REFERENCE.md）

# 2. 测试
python -c "from my_handlers.my_factors import MyFactors; print('OK')"

# 3. 配置
# 在配置中使用新的 handler
# handler:
#   class: "MyFactors"
#   module_path: "my_handlers.my_factors"

# 4. 运行
python scripts/run_routine_mlflow.py --config config/online_config.yaml
```

### 场景 4: 添加自定义策略

```bash
# 1. 创建 Strategy
mkdir -p my_strategies
# 编辑 my_strategies/my_strategy.py（参考 docs/CUSTOM_STRATEGY_GUIDE.md）

# 2. 配置
# type: "Custom"
# class: "MyStrategy"
# module_path: "my_strategies.my_strategy"

# 3. 运行
python scripts/run_routine_mlflow.py --config config/online_config.yaml
```

---

## 📊 MLflow 集成详解

### 自动记录的内容

#### 训练指标
- `train_loss` - 训练损失
- `valid_loss` - 验证损失
- `train_time_seconds` - 训练耗时
- 模型参数（n_estimators, num_leaves等）

#### 预测指标
- `ic` - Information Coefficient
- `rank_ic` - Rank IC
- `ic_std` - IC 标准差

#### 回测指标
- `total_return` - 累计收益
- `annual_return` - 年化收益
- `sharpe_ratio` - 夏普比率
- `max_drawdown` - 最大回撤
- `win_rate` - 胜率
- `excess_return` - 超额收益
- `information_ratio` - 信息比率

#### 图表（Artifacts）
- `feature_importance.png` - 特征重要性
- `portfolio_returns.png` - 收益曲线
- `returns_distribution.png` - 收益分布

### MLflow UI 使用

```bash
# 启动
mlflow ui --port 5000

# 访问
http://localhost:5000

# 操作
1. 选择 Experiments
2. 查看 Runs 列表
3. 点击 Run 查看详情
4. 勾选多个 Runs -> Compare 对比
5. 查看图表和指标
```

---

## 🎓 学习路径

### 初学者
1. 阅读 `QUICKSTART.md`
2. 使用 `config/online_config_simple.yaml`
3. 运行 `first_run.py` 和 `run_routine.py`

### 进阶用户
1. 阅读 `docs/QUICK_REFERENCE.md`
2. 添加自定义因子
3. 启用 MLflow 集成

### 高级用户
1. 阅读 `docs/CUSTOM_STRATEGY_GUIDE.md`
2. 开发自定义策略
3. 阅读 `docs/MLFLOW_GUIDE.md`
4. 完整的实验管理和对比

---

## 📖 文档导航

### 核心文档
- **README.md** - 完整功能说明
- **QUICKSTART.md** - 5分钟快速开始
- **PROJECT_STRUCTURE.md** - 项目架构

### 自定义相关
- **docs/QUICK_REFERENCE.md** - ⭐ 自定义策略快速参考
- **docs/CUSTOM_STRATEGY_GUIDE.md** - 详细教程
- **docs/HOW_TO_ADD_CUSTOM.md** - 添加自定义指南
- **examples/** - 可运行的示例代码

### MLflow 相关
- **docs/MLFLOW_QUICKSTART.md** - ⭐ 5分钟上手 MLflow
- **docs/MLFLOW_GUIDE.md** - MLflow 完整指南
- **config/online_config_mlflow.yaml** - MLflow 配置示例
- **scripts/*_mlflow.py** - 带 MLflow 的脚本

---

## 🔑 关键代码

### MLflow 集成核心

```python
# 1. 创建 MLflow Logger
mlflow_logger = MLflowLogger(
    experiment_name="qlib_online",
    tracking_uri="http://localhost:5000"
)

# 2. 包装策略
mlflow_strategy = MLflowEnabledStrategy(strategy, mlflow_logger)

# 3. 训练时自动记录
mlflow_strategy.prepare_online_models(models)  # 自动记录指标

# 4. 回测分析
analyzer = QlibBacktestAnalyzer(mlflow_logger)
analyzer.analyze_and_log(predictions, returns)  # 自动生成图表
```

### 自定义 Handler

```python
from qlib.data.dataset.processor import Processor

class MyHandler(Processor):
    def __init__(self, fit_start_time, fit_end_time, **kwargs):
        super().__init__(fit_start_time, fit_end_time)

    def __call__(self, df: pd.DataFrame) -> pd.DataFrame:
        df['my_factor'] = df['close'].pct_change(20)
        return df
```

### 自定义 Strategy

```python
from qlib.workflow.online.strategy import OnlineStrategy

class MyStrategy(OnlineStrategy):
    def prepare_tasks(self, cur_time, **kwargs):
        # 自定义逻辑
        if need_retrain:
            return [self.task_template.copy()]
        return []
```

---

## 🛠️ 常用命令

```bash
# 配置验证
python scripts/test_config.py --config config/online_config.yaml

# 查看状态
python scripts/run_routine.py --config config/online_config.yaml --status

# 获取信号
python scripts/get_signals.py --config config/online_config.yaml --top 30

# 评估策略
python scripts/evaluate.py --config config/online_config.yaml --start 2023-01-01 --end 2024-01-01

# 策略管理
python scripts/upgrade_strategy.py --config config/online_config.yaml list
python scripts/upgrade_strategy.py --config config/online_config.yaml add

# MLflow 相关
python scripts/first_run_mlflow.py --config config/online_config_mlflow.yaml
python scripts/run_routine_mlflow.py --config config/online_config_mlflow.yaml

# 启动 MLflow UI
mlflow ui --port 5000
```

---

## 🐳 Docker 部署

```bash
# 构建镜像
docker build -t fin-qlib .

# 启动服务（包含 MLflow + MongoDB）
docker-compose up -d

# 访问 MLflow UI
http://localhost:5000

# 查看 MongoDB
mongodb://localhost:27017
```

---

## 📈 最佳实践

1. **使用 MLflow 跟踪所有实验**
   - 每次训练/回测自动记录
   - 方便对比和调试

2. **定期评估策略**
   - 使用 `evaluate.py` 对比性能
   - 在 MLflow UI 中查看趋势

3. **渐进式上线**
   - Shadow → 小流量 → 全量
   - 使用 MLflow 对比新旧策略

4. **监控告警**
   - 设置关键指标阈值
   - Sharpe < 0.5 时告警

5. **定期备份**
   - 备份 `checkpoints/` 目录
   - 导出 MLflow 实验数据

---

## 🎉 项目亮点

1. **配置驱动** - 无需修改代码即可添加策略
2. **MLflow 深度集成** - 自动记录所有指标和图表
3. **完整示例** - 从简单到复杂的完整示例
4. **详细文档** - 12个文档文件覆盖所有场景
5. **生产就绪** - Docker、Cron、日志、错误处理

---

## 📞 获取帮助

- 查看 `docs/` 目录下的详细文档
- 检查 `examples/` 中的示例代码
- 运行 `test_config.py` 验证配置
- 查看 MLflow UI 进行调试

---

## 📄 文件清单

### 核心文件（16个）
- 3个核心代码文件
- 8个脚本文件
- 4个配置文件
- 1个依赖文件

### 文档文件（12个）
- 4个主要文档
- 8个详细指南

### 示例文件（2个）
- Handler 示例
- Strategy 示例

**总计：30+ 文件**，完整的量化交易在线管理系统
