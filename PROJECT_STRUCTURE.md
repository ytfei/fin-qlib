# Fin-Qlib 项目概览

## 项目创建时间
2024年

## 项目目标
基于 Qlib 的在线模型管理最佳实践，提供生产级别的量化交易模型管理系统。

## 目录结构

```
fin-qlib/
├── README.md                      # 详细文档
├── QUICKSTART.md                  # 快速入门指南
├── PROJECT_STRUCTURE.md           # 本文件
├── requirements.txt               # Python依赖
├── Dockerfile                     # Docker镜像
├── docker-compose.yml             # Docker编排
├── deploy.sh                      # 部署脚本
│
├── config/                        # 配置文件目录
│   ├── online_config_template.yaml   # 完整配置模板
│   └── online_config_simple.yaml     # 简化配置（测试用）
│
├── scripts/                       # 可执行脚本
│   ├── test_config.py                # 配置验证脚本
│   ├── first_run.py                  # 初始化和首次训练
│   ├── run_routine.py                # 定期更新脚本（cron调用）
│   ├── evaluate.py                   # 策略评估脚本
│   ├── get_signals.py                # 导出交易信号
│   ├── upgrade_strategy.py           # 策略管理（添加/删除）
│   └── make_executable.sh            # 批量设置可执行权限
│
├── src/                           # 源代码
│   ├── __init__.py
│   ├── managed_manager.py            # 核心类：ManagedOnlineManager
│   └── ensemble.py                   # 集成方法实现
│
├── checkpoints/                   # 自动创建：模型检查点
│   └── online_manager.pkl           # OnlineManager状态文件
│
├── logs/                          # 自动创建：日志文件
│   └── online_manager_YYYYMMDD.log
│
└── signals/                       # 自动创建：导出的交易信号
    ├── signals_latest.csv           # 最新信号
    └── signals_YYYYMMDD.csv         # 历史信号
```

## 核心组件说明

### 1. ManagedOnlineManager (src/managed_manager.py)

**职责**：
- 配置驱动的 OnlineManager 包装器
- 策略动态管理
- 信号生成和导出
- 状态持久化

**主要方法**：
```python
# 初始化
manager = ManagedOnlineManager("config/online_config.yaml")

# 同步策略（添加/删除）
manager.sync_strategies()

# 执行日常更新
manager.run_routine()

# 评估策略
results = manager.evaluate_strategies("2023-01-01", "2024-01-01")

# 获取信号
signals = manager.get_signals()
```

### 2. 集成方法 (src/ensemble.py)

**支持的集成方法**：

| 方法 | 描述 | 使用场景 |
|------|------|---------|
| `AverageEnsemble` | 等权重平均 | 模型性能相近 |
| `WeightedEnsemble` | 固定权重加权 | 已知的最佳权重 |
| `BestModelEnsemble` | 选择最佳单模型 | 某模型显著优于其他 |
| `DynamicWeightEnsemble` | 动态权重调整 | 需要自适应权重 |
| `VotingEnsemble` | 投票机制 | 降低单模型风险 |

### 3. 脚本工具

| 脚本 | 用途 | 调用频率 |
|------|------|---------|
| `test_config.py` | 验证配置文件 | 修改配置后 |
| `first_run.py` | 初始化和首次训练 | 一次性 |
| `run_routine.py` | 日常更新 | 每天/每周 |
| `evaluate.py` | 策略评估 | 按需 |
| `get_signals.py` | 导出信号 | 按需 |
| `upgrade_strategy.py` | 箖略管理 | 添加新模型时 |

## 工作流程

### 初始化流程

```
1. 创建配置文件
   └─> cp config/online_config_simple.yaml config/online_config.yaml

2. 验证配置
   └─> python scripts/test_config.py --config config/online_config.yaml

3. 首次训练
   └─> python scripts/first_run.py --config config/online_config.yaml
       ├─> 初始化 Qlib
       ├─> 创建 OnlineManager
       ├─> 训练初始模型
       └─> 保存检查点
```

### 日常更新流程

```
触发方式：
├─> 手动：python scripts/run_routine.py --config config/online_config.yaml
└─> 自动：cron 每日 16:30 执行

执行步骤：
├─> 加载 Manager 检查点
├─> sync_strategies() - 同步配置（如果指定 --sync）
├─> routine()
│   ├─> prepare_tasks() - 检查是否需要新模型
│   ├─> train() - 训练新模型
│   ├─> prepare_online_models() - 切换在线模型
│   ├─> update_online_pred() - 更新预测
│   └─> prepare_signals() - 生成交易信号
└─> 保存检查点 + 导出信号
```

### 新模型上线流程

```
1. 开发阶段（本地测试）
   └─> 使用 simulate() 回测验证

2. 添加到配置（shadow mode）
   └─> enabled: false

3. 灰度阶段（小流量）
   └─> signal_config.ensemble_method = "weighted"
       weights: {old: 0.9, new: 0.1}

4. 全量阶段
   └─> signal_config.ensemble_method = "dynamic"
```

## 配置要点

### 策略配置

```yaml
strategies:
  - name: "LGB_Alpha158"        # 唯一标识符
    enabled: true               # 是否启用
    type: "RollingStrategy"     # 策略类型

    task_template:              # 模型配置
      model:
        class: "LGBModel"
        module_path: "qlib.contrib.model.gbdt"
      dataset:
        class: "DatasetH"
        segments:
          train: ("2020-01-01", "2022-01-01")
          valid: ("2022-01-01", "2022-07-01")
          test: ("2022-07-01", "2023-01-01")

    rolling_config:             # 滚动配置
      step: 550                 # 滚动步长（交易日）
      rtype: "ROLL_SD"          # SD=滑动窗口, EX=扩展窗口
```

### 信号配置

```yaml
signal_config:
  ensemble_method: "dynamic"    # 集成方法

  # method = "weighted" 时使用
  weights:
    LGB_Alpha158: 0.6
    XGB_Alpha158: 0.4

  # method = "dynamic" 时使用
  lookback_days: 30            # 回看天数
  metric: "ic"                 # 评估指标

  # method = "voting" 时使用
  top_n: 50                    # 每个模型选出的股票数
  min_votes: 2                 # 最少投票数
```

## 部署方案

### 方案 A：Cron（推荐）

```bash
# 编辑 crontab
crontab -e

# 添加：
30 16 * * 1-5 cd /path/to/fin-qlib && python scripts/run_routine.py --config config/online_config.yaml >> logs/routine.log 2>&1
```

### 方案 B：Systemd Timer

```bash
# 创建服务文件
sudo nano /etc/systemd/system/fin-qlib.service

# 创建 timer
sudo nano /etc/systemd/system/fin-qlib.timer

# 启用
sudo systemctl enable fin-qlib.timer
sudo systemctl start fin-qlib.timer
```

### 方案 C：Docker

```bash
# 构建镜像
docker build -t fin-qlib .

# 运行容器
docker-compose up -d

# 或使用宿主机 cron 触发容器内任务
# 30 16 * * 1-5 docker exec fin-qlib python scripts/run_routine.py
```

## 监控和日志

### 日志位置

```
logs/
├── online_manager_20240115.log    # 当天日志
└── routine.log                    # cron 输出（如果配置）
```

### 监控指标

建议监控以下指标：
1. 模型训练是否成功
2. 信号生成数量
3. 预测更新是否完整
4. 在线模型切换频率

### 健康检查

```bash
# 检查状态
python scripts/run_routine.py --config config/online_config.yaml --status

# 查看在线模型
python scripts/upgrade_strategy.py --config config/online_config.yaml list
```

## 最佳实践

1. **版本控制**：配置文件纳入 Git，检查点定期备份
2. **渐进式上线**：新模型先 shadow → 小流量 → 全量
3. **监控告警**：设置 training/prediction 失败告警
4. **定期评估**：每月运行 evaluate.py 对比策略
5. **配置分离**：开发/测试/生产环境使用不同配置

## 常见问题

**Q: 如何修改滚动步长？**
A: 修改配置中的 `rolling_config.step`

**Q: 如何添加新特征？**
A: 修改 `task_template.dataset.kwargs.handler` 为新的 handler 类

**Q: 如何回滚到旧模型？**
A: 在配置中禁用新策略 `enabled: false`，重新运行 routine

**Q: 如何清空所有数据重新开始？**
A: `python scripts/first_run.py --config config/online_config.yaml --reset`

## 相关文档

- [README.md](README.md) - 完整使用文档
- [QUICKSTART.md](QUICKSTART.md) - 5分钟快速开始
- [Qlib 官方文档](https://qlib.readthedocs.io/)
