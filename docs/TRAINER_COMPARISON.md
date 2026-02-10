# Trainer 对比详解

## Qlib 中的 Trainer 类型

Qlib 提供了 4 种 Trainer 实现：

| Trainer | 全称 | 含义 | 适用场景 |
|---------|------|------|---------|
| `TrainerR` | Trainer Recorder | 基于 Recorder 的训练器 | 单进程、简单场景 |
| `TrainerRM` | Trainer Recorder Manager | 基于 Recorder + TaskManager 的训练器 | 多进程、分布式 |
| `DelayTrainerR` | Delay Trainer Recorder | 延迟训练版本（Recorder） | 回测、模拟 |
| `DelayTrainerRM` | Delay Trainer Recorder Manager | 延迟训练版本（Manager） | 回测 + 多进程 |

---

## 核心区别

### 1. 训练时机

```
TrainerR / TrainerRM:
├─ train() 方法
│   └─> 立即执行模型训练 ✅
│   └─> 等待训练完成后返回
│
└─ end_train() 方法
    └─> 仅做收尾工作

DelayTrainerR / DelayTrainerRM:
├─ train() 方法
│   └─> 只创建 Recorder，保存任务配置 ⏸️
│   └─> 不执行实际训练
│   └─> 立即返回（非阻塞）
│
└─ end_train() 方法
    └─> 此时才执行真正的模型训练 ✅
```

---

## 详细对比

### TrainerR (Trainer Recorder)

**特点**：
- ✅ 最简单
- ✅ 基于 MLflow Recorder
- ✅ 单进程顺序训练
- ❌ 不支持分布式

**工作流程**：

```python
trainer = TrainerR()

# 1. train() - 立即训练
models = trainer.train([task1, task2, task3])
    ├─> 训练 task1  ████████ (等待完成)
    ├─> 训练 task2  ████████ (等待完成)
    └─> 训练 task3  ████████ (等待完成)

# 总耗时: 3个任务串行执行

# 2. end_train() - 收尾
models = trainer.end_train(models)
    └─> 几乎不做任何事（训练已在 train 中完成）
```

**代码示例**：

```python
from qlib.model.trainer import TrainerR

trainer = TrainerR(
    experiment_name="my_exp",
    call_in_subproc=False  # 是否在子进程中运行
)

manager = OnlineManager(
    strategies=[strategy],
    trainer=trainer
)
```

**适用场景**：
- ✅ 快速实验
- ✅ 任务数量少（1-3个）
- ✅ 单机训练
- ✅ 内存充足

**不适用场景**：
- ❌ 大量任务训练
- ❌ 需要分布式
- ❌ 需要并行训练

---

### TrainerRM (Trainer Recorder Manager)

**特点**：
- ✅ 基于 TaskManager + MongoDB
- ✅ 支持多进程/多机并行
- ✅ 任务队列管理
- ✅ 可扩展性强

**工作流程**：

```python
trainer = TrainerRM(
    experiment_name="my_exp",
    task_pool="my_tasks"  # MongoDB 集合
)

# 1. train() - 提交任务到队列
models = trainer.train([task1, task2, task3])
    ├─> 将任务保存到 MongoDB
    ├─> 调度 run_task() 进行训练
    │   ├─> Worker 1: task1  ████████ (并行)
    │   ├─> Worker 2: task2  ████████ (并行)
    │   └─> Worker 3: task3  ████████ (并行)
    └─> 等待所有任务完成

# 2. end_train() - 收尾
models = trainer.end_train(models)
    └─> 更新任务状态
```

**代码示例**：

```python
import qlib

# 配置 MongoDB
mongo_config = {
    "task_url": "mongodb://localhost:27017/",
    "task_db_name": "qlib_tasks"
}

qlib.init(
    provider_uri="~/.qlib/qlib_data/cn_data",
    region="cn",
    mongo=mongo_config  # 启用 MongoDB
)

trainer = TrainerRM(
    experiment_name="my_exp",
    task_pool="task_pool_name"  # MongoDB 集合名
)

manager = OnlineManager(
    strategies=[strategy],
    trainer=trainer
)
```

**适用场景**：
- ✅ 大量任务训练（10+个）
- ✅ 需要并行加速
- ✅ 多机训练
- ✅ 任务队列管理
- ✅ 生产环境

**不适用场景**：
- ❌ 简单快速实验（MongoDB 配置复杂）

**Worker 模式**：

```python
# 启动 Worker 进程（在其他机器或进程中）
trainer.worker()
    └─> 持续监听 MongoDB 任务队列
    └─> 自动获取并训练任务
```

---

### DelayTrainerR (延迟训练 - Recorder 版本)

**特点**：
- ⏸️ 延迟训练：train() 不训练，end_train() 才训练
- ✅ 用于回测/模拟场景
- ✅ 可以批量准备所有任务
- ✅ 最后统一训练

**工作流程**：

```python
trainer = DelayTrainerR()

# 模拟回测
manager.simulate(
    end_time="2025-01-01",
    frequency="day"
)

# 内部执行流程：
# for day in [2023-01-01, 2023-01-02, ...]:
#     1. prepare_tasks()      → 检查是否需要新任务
#         └─> 如果需要：train()  → 只创建 Recorder ⏸️
#     2. prepare_online_models() → 标记模型（未训练）
#     3. prepare_signals()      → 生成信号（基于旧模型）
#
# 模拟完成后：
# 4. delay_prepare()
#     └─> 此时才真正训练所有模型 ✅
```

**为什么需要延迟训练？**

**问题**：在回测历史时，如果每个时间点都训练模型：
```
2023-01-01: 训练模型1 (耗时10分钟)
2023-01-02: 训练模型2 (耗时10分钟)  ← 还未完成
...
回测会非常慢！
```

**解决**：延迟训练
```
# 第一阶段：快速模拟
2023-01-01: 创建任务1 ⏸️ (几毫秒)
2023-01-02: 创建任务2 ⏸️ (几毫秒)
...
模拟很快完成

# 第二阶段：批量训练
所有任务：[task1, task2, ...]
    ├─> Worker 1: task1  (并行)
    ├─> Worker 2: task2  (并行)
    └─> ...
一次性完成所有训练
```

**适用场景**：
- ✅ 历史回测（simulate）
- ✅ 快速验证策略
- ✅ 模型无时间依赖
- ✅ 有并行计算资源

**不适用场景**：
- ❌ 实盘交易（需要实时模型）

---

### DelayTrainerRM (延迟训练 - Manager 版本)

**特点**：
- ⏸️ 延迟训练 + 🚀 多进程/多机
- ✅ 最强大的训练方式
- ✅ 适合大规模回测

**工作流程**：

```python
trainer = DelayTrainerRM(
    experiment_name="my_exp",
    task_pool="my_tasks"
)

# 回测模拟
manager.simulate(
    end_time="2025-01-01"
)

# 第一阶段：快速模拟
for day in historical_days:
    prepare_tasks()  → 提交到 MongoDB ⏸️
    prepare_online_models()
    prepare_signals()

# 第二阶段：批量并行训练
delay_prepare()
    └─> MongoDB 中的所有任务
        └─> 多个 Worker 并行训练 ✅
```

**适用场景**：
- ✅ 大规模回测
- ✅ 多机回测
- ✅ 需要快速验证
- ✅ 有计算集群

---

## 完整对比表

| 维度 | TrainerR | TrainerRM | DelayTrainerR | DelayTrainerRM |
|------|----------|-----------|---------------|----------------|
| **训练时机** | 立即 | 立即 | 延迟 | 延迟 |
| **并行支持** | ❌ | ✅ | ✅ | ✅ |
| **任务管理** | 内存 | MongoDB | 内存 | MongoDB |
| **Worker 支持** | ❌ | ✅ | ✅ | ✅ |
| **适用场景** | 实验 | 生产 | 回测 | 回测+生产 |
| **复杂度** | 低 | 中 | 中 | 高 |
| **MongoDB 依赖** | ❌ | ✅ | ❌ | ✅ |
| **内存需求** | 高 | 低 | 低 | 低 |

---

## 使用建议

### 场景 1: 快速实验（初学者）

```python
# 使用 TrainerR - 最简单
trainer = TrainerR()

manager = OnlineManager(
    strategies=[strategy],
    trainer=trainer
)
```

### 场景 2: 生产环境（单机）

```python
# 使用 TrainerRM - 支持并行
trainer = TrainerRM(
    task_pool="production_tasks"
)

manager = OnlineManager(
    strategies=[strategy],
    trainer=trainer
)

# 可以启动 Worker 进程
trainer.worker()
```

### 场景 3: 回测模拟

```python
# 使用 DelayTrainerR 或 DelayTrainerRM
trainer = DelayTrainerR()  # 单机

# 或
trainer = DelayTrainerRM()  # 多机

manager.simulate(
    end_time="2025-01-01",
    frequency="day"
)

# 所有任务会延迟到最后统一训练
```

### 场景 4: 大规模回测（多机）

```python
# 使用 DelayTrainerRM - 最强大
trainer = DelayTrainerRM(
    task_pool="backtest_tasks"
)

# 机器 A: 运行主程序
manager.simulate(...)

# 机器 B, C, D: 运行 Worker
trainer.worker()  # 持续监听并训练
```

---

## 配置示例

### 配置 1: TrainerR（默认）

```yaml
online_manager:
  trainer:
    type: "TrainerR"

qlib_config:
  provider_uri: "~/.qlib/qlib_data/cn_data"
  region: "cn"
  # 不需要 MongoDB
```

### 配置 2: TrainerRM（生产）

```yaml
online_manager:
  trainer:
    type: "TrainerRM"

qlib_config:
  provider_uri: "~/.qlib/qlib_data/cn_data"
  region: "cn"

  # MongoDB 配置
  mongo:
    enabled: true
    task_url: "mongodb://localhost:27017/"
    task_db_name: "qlib_online"
```

### 配置 3: DelayTrainerRM（回测）

```yaml
# 在模拟代码中使用
trainer = DelayTrainerRM(
    experiment_name="backtest",
    task_pool="backtest_tasks"
)

manager = OnlineManager(
    strategies=[strategy],
    trainer=trainer
)

# 运行模拟
manager.simulate(end_time="2025-01-01")
```

---

## 代码示例

### 示例 1: 简单训练

```python
from qlib.model.trainer import TrainerR

trainer = TrainerR()

# 训练任务
models = trainer.train([task1, task2])
# → 串行执行
# → task1 完成后才开始 task2
```

### 示例 2: 并行训练

```python
from qlib.model.trainer import TrainerRM

trainer = TrainerRM(
    task_pool="my_pool"
)

# 训练任务（提交到队列）
models = trainer.train([task1, task2, task3])
# → 任务提交到 MongoDB
# → Worker 进程自动获取并训练
# → 多个任务并行执行
```

### 示例 3: 回测

```python
from qlib.model.trainer import DelayTrainerRM

trainer = DelayTrainerRM(
    task_pool="backtest_pool"
)

manager = OnlineManager(
    strategies=[strategy],
    trainer=trainer
)

# 回测
manager.simulate(end_time="2025-01-01")
# → 快速模拟整个历史
# → 只创建任务，不训练
# → 模拟完成后批量训练
```

---

## 选择建议

```
你的需求
    │
    ├─ 快速实验、任务少？
    │   └─> TrainerR ✅
    │
    ├─ 生产环境、多任务？
    │   └─> TrainerRM ✅
    │
    ├─ 历史回测、快速验证？
    │   └─> DelayTrainerR ✅
    │       或
    │   └─> DelayTrainerRM ✅ (多机)
    │
    └─ 大规模回测、多机？
        └─> DelayTrainerRM ✅
```

---

## 关键要点总结

### TrainerR
- 📌 最简单
- 📌 单进程
- 📌 不需要 MongoDB
- 📌 适合：实验、少量任务

### TrainerRM
- 📌 生产级
- 📌 支持并行
- 📌 需要 MongoDB
- 📌 适合：多任务、分布式

### DelayTrainerR
- 📌 延迟训练
- 📌 单机并行
- 📌 不需要 MongoDB
- 📌 适合：回测、快速验证

### DelayTrainerRM
- 📌 延迟训练 + 并行
- 📌 最强大
- 📌 需要 MongoDB
- 📌 适合：大规模回测、多机

---

## 实际使用建议

### 开发阶段

```python
# 使用 TrainerR
trainer = TrainerR()
# 快速迭代，无需配置 MongoDB
```

### 回测阶段

```python
# 使用 DelayTrainerRM
trainer = DelayTrainerRM()
# 快速模拟历史，最后批量训练
```

### 生产阶段

```python
# 使用 TrainerRM
trainer = TrainerRM()
# 支持并行，支持 Worker 扩展
```

---

## 相关文档

- Qlib 官方文档: [Training Task](https://qlib.readthedocs.io/en/latest/component/trainer.html)
- 项目配置: `config/online_config_mlflow.yaml`
