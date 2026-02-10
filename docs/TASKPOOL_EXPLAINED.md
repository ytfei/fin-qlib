# TaskPool 详解 - MongoDB 任务队列

## 📌 task_pool 是什么？

**简单来说**：`task_pool` 就是 **MongoDB 中的一个集合名称**，用作任务队列。

```python
TrainerRM(task_pool="production")
#                  ↑
#                  MongoDB 集合名称
```

---

## 🗄️ MongoDB 结构

### 数据库层级

```
MongoDB 服务器
    └─ qlib_tasks (数据库)
        ├─ production (集合)  ← task_pool="production"
        ├─ backtest (集合)    ← task_pool="backtest"
        ├─ experiment_A (集合) ← task_pool="experiment_A"
        └─ ...
```

### 集合中的文档结构

```javascript
// MongoDB 集合中的一个任务文档
{
  "_id": ObjectId("..."),

  "def": Binary(pickle.dumps({
    "model": {...},
    "dataset": {...}
  })),

  "filter": {
    "strategy": "LGB_rolling",
    "status": "waiting"
  },

  "status": "waiting",  // waiting | running | part_done | done

  "res": Binary(pickle.dumps({
    // 训练结果（模型、预测等）
  }))
}
```

---

## 🔄 任务流程

### 完整流程图

```
┌─────────────────────────────────────────────────────────────┐
│                  TrainerRM 工作流程                           │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  1. 主进程提交任务                                           │
│                                                               │
│  trainer.train([task1, task2, task3])                        │
│       │                                                       │
│       ├─> TaskManager(task_pool="production")                │
│       │   └─> 连接 MongoDB 数据库                              │
│       │   └─> 访问集合: qlib_tasks.production              │
│       │                                                       │
│       ├─> 创建任务文档                                         │
│       │   ├─> task1 → {"status": "waiting"}                   │
│       │   ├─> task2 → {"status": "waiting"}                   │
│       │   └─> task3 → {"status": "waiting"}                   │
│       │       (保存在 MongoDB 中)                               │
│       │                                                       │
│       └─> 调度 Worker 进程                                     │
│           run_task(                                           │
│               task_pool="production",                         │
│               query={"status": "waiting"}                     │
│           )                                                  │
│                                                               │
│  2. Worker 进程获取任务                                       │
│                                                               │
│  worker() (在其他进程/机器中运行)                            │
│    │                                                          │
│    └─> 连接 MongoDB                                            │
│        └─> 查询: db.production.find({"status": "waiting"})   │
│        └─> 找到 task1                                         │
│            └─> 更新状态: "waiting" → "running"                  │
│            └─> 获取任务定义                                   │
│                ├─> model: {...}                               │
│                └─> dataset: {...}                             │
│            └─> 训练模型 ████████                                │
│            └─> 保存结果                                      │
│            └─> 更新状态: "running" → "done"                    │
│        └─> 继续查找下一个任务...                             │
│                                                               │
│  3. 主进程等待完成                                           │
│                                                               │
│  trainer.train() 等待所有 Worker 完成后返回                  │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎯 task_pool 的作用

### 1. 任务隔离

**问题**：不同场景的任务混在一起怎么办？

```
MongoDB 数据库:
├─ production 集合    ← 实盘交易任务
│   ├─ task_001 (waiting)
│   ├─ task_002 (running)
│   └─ task_003 (done)
│
├─ backtest 集合      ← 回测任务
│   ├─ task_101 (waiting)
│   └─ task_102 (done)
│
└─ experiment_A 集合  ← 实验 A 的任务
    ├─ task_201 (waiting)
    └─ task_202 (done)
```

**解决**：通过 `task_pool` 参数隔离不同场景的任务

```python
# 生产环境
prod_trainer = TrainerRM(task_pool="production")

# 回测环境
backtest_trainer = TrainerRM(task_pool="backtest")

# 实验 A
exp_a_trainer = TrainerRM(task_pool="experiment_A")
```

---

### 2. 任务状态管理

**任务状态机**：

```
waiting → running → part_done → done
   ↑          ↓
   └─────── (失败重试)
```

**在 MongoDB 中查询**：

```python
# 只获取等待中的任务
query = {"status": "waiting"}
tasks = list(mongo.find(query))

# 只获取特定状态的任务
query = {"status": {"$in": ["waiting", "running"]}}
tasks = list(mongo.find(query))

# 获取特定策略的任务
query = {"filter.strategy": "LGB_rolling"}
tasks = list(mongo.find(query))
```

---

### 3. 分布式训练

**多机器训练架构**：

```
┌─────────────────────────────────────────────────────────────┐
│                   分布式训练架构                             │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  机器 A (主进程)                                             │
│  ├─ trainer.train([task1, ..., task10])                     │
│  │   └─> 提交任务到 MongoDB                               │
│  │       task_pool="production"                             │
│  │       ↓                                                │
│  │   MongoDB Server (192.168.1.100)                      │
│  │       └─> task_01, task_02, ..., task_10                │
│  │                                                          │
│  机器 B (Worker)                                              │
│  ├─ trainer.worker()                                       │
│  │   └─> 连接 MongoDB                                     │
│  │   └─> 获取 task_01, task_02                             │
│  │       ├─> 训练 task_01 ████████                          │
│  │       └─> 训练 task_02 ████████                          │
│  │                                                          │
│  机器 C (Worker)                                              │
│  ├─ trainer.worker()                                       │
│  │   └─> 连接 MongoDB                                     │
│  │   └─> 获取 task_03, task_04                             │
│  │       ├─> 训练 task_03 ████████                          │
│  │       └─> 训练 task_04 ████████                          │
│  │                                                          │
│  ... (更多 Worker 机器)                                       │
│                                                               │
│  结果: 所有任务并行完成，时间大幅缩短                      │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 💻 代码示例

### 示例 1: 基础使用

```python
import qlib
from qlib.model.trainer import TrainerRM

# 配置 MongoDB
qlib.init(
    provider_uri="~/.qlib/qlib_data/cn_data",
    region="cn",
    mongo={
        "task_url": "mongodb://localhost:27017/",
        "task_db_name": "qlib_tasks"
    }
)

# 创建 Trainer
trainer = TrainerRM(
    task_pool="production"  # MongoDB 集合名称
)

# 使用
manager = OnlineManager(
    strategies=[strategy],
    trainer=trainer
)
```

**发生了什么**：

```
1. trainer.train([task1, task2])

2. 在 MongoDB 中:
   database: qlib_tasks
   collection: production  ← task_pool 指定的集合
   documents:
     - {_id: "...", status: "waiting", def: Binary(task1)}
     - {_id: "...", status: "waiting", def: Binary(task2)}

3. Worker 进程从 "production" 集合中获取任务
```

---

### 示例 2: 多场景隔离

```python
# 生产环境
prod_trainer = TrainerRM(task_pool="production")

# 测试环境
test_trainer = TrainerRM(task_pool="testing")

# 回测环境
backtest_trainer = TrainerRM(task_pool="backtest")

# 实验 A
exp_a_trainer = TrainerRM(task_pool="exp_a_20240115")

# 每个 trainer 使用不同的 MongoDB 集合
# 任务完全隔离，互不干扰
```

---

### 示例 3: 查看 MongoDB 中的任务

```python
from pymongo import MongoClient

# 连接 MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client["qlib_tasks"]
collection = db["production"]

# 查看所有任务
for task in collection.find():
    print(f"Task ID: {task['_id']}")
    print(f"Status: {task['status']}")
    print(f"Filter: {task.get('filter', {})}")
    print("-" * 40)
```

**输出示例**：

```
Task ID: 65f12a34...
Status: waiting
Filter: {'strategy': 'LGB_rolling'}
----------------------------------------
Task ID: 65f12b56...
Status: done
Filter: {'strategy': 'XGB_rolling'}
----------------------------------------
```

---

### 示例 4: 启动 Worker 进程

```python
from qlib.model.trainer import TrainerRM

trainer = TrainerRM(task_pool="production")

# 启动 Worker（在单独的终端/进程中）
trainer.worker()
```

**Worker 做什么**：

```
无限循环:
    1. 连接 MongoDB
    2. 查询: {"status": "waiting"}
    3. 找到任务
        → 更新为 "running"
        → 训练模型
        → 保存结果
        → 更新为 "done"
    4. 继续查找下一个任务
    ...
```

---

## 🔧 task_pool 命名规范

### 常见命名方式

```python
# 1. 按环境命名
task_pool="production"      # 生产环境
task_pool="testing"          # 测试环境
task_pool="development"      # 开发环境

# 2. 按日期命名
task_pool="backtest_20240115" # 特定日期的回测
task_pool="exp_001"            # 实验 001

# 3. 按策略命名
task_pool="LGB_rolling_tasks"
task_pool="XGB_tasks"

# 4. 按用途命名
task_pool="online_training"    # 在线训练
task_pool="offline_analysis"   # 离线分析
```

### 推荐命名

```python
# 生产环境（固定）
task_pool="production"

# 每次回测使用新的 pool
task_pool=f"backtest_{datetime.now():%Y%m%d}"

# 每个实验使用新的 pool
task_pool=f"experiment_{experiment_id}"
```

---

## 🎯 为什么需要 task_pool？

### 问题 1: 任务持久化

**没有 task_pool**（TrainerR）：
```
任务只存在于内存中
├─> 进程崩溃 → 任务丢失 ❌
├─> 机器重启 → 任务丢失 ❌
└─> 无法恢复
```

**有 task_pool**（TrainerRM）：
```
任务保存在 MongoDB 中
├─> 进程崩溃 → 任务仍在 MongoDB ✅
├─> Worker 可以继续训练 ✅
└─> 任务可以暂停、恢复 ✅
```

### 问题 2: 分布式训练

**没有 task_pool**：
```
单机训练
├─> CPU: 8 核
├─> 任务: 20 个
└─> 耗时: 20 × 10分钟 = 200分钟
```

**有 task_pool**：
```
分布式训练
├─> 机器 A: 8 核 → 训练 5 个任务
├─> 机器 B: 8 核 → 训练 5 个任务
├─> 机器 C: 8 核 → 训练 10 个任务
└─> 耗时: 10 / 3 = 3.3分钟 (6倍加速)
```

### 问题 3: 任务管理

**没有 task_pool**：
```
无法追踪任务状态
不知道哪些任务已完成
无法暂停/恢复任务
```

**有 task_pool**：
```
完整的任务状态管理
✅ waiting → running → done
✅ 可查询任务进度
✅ 可重试失败的任务
✅ 可查看历史任务
```

---

## 📊 task_pool vs 普通 Python 列表

| 特性 | task_pool (MongoDB) | Python List |
|------|----------------------|------------|
| **持久化** | ✅ 永久保存 | ❌ 进程结束丢失 |
| **分布式** | ✅ 多机共享 | ❌ 单机 |
| **状态管理** | ✅ 完整状态机 | ❌ 无状态 |
| **可扩展** | ✅ 添加 Worker 扩容 | ❌ 受限于单机 |
| **查询能力** | ✅ MongoDB 查询 | ❌ 无法查询 |
| **可靠性** | ✅ 高 | ❌ 低 |

---

## 🛠️ 实际操作

### 查看所有 task_pool

```bash
# 命令行工具
python -m qlib.workflow.task.manage list

# 输出:
# production
# backtest_20240115
# experiment_001
```

### 查看任务统计

```bash
# 查看特定 pool 的任务状态
python -m qlib.workflow.task.manage -t production task_stat

# 输出:
# Total tasks: 20
# waiting: 5
# running: 3
# done: 12
```

### 等待任务完成

```bash
# 等待所有任务完成
python -m qlib.workflow.task.manage -t production wait

# 会阻塞直到所有任务状态为 "done"
```

---

## 💡 最佳实践

### 1. 环境隔离

```python
# 开发环境
dev_trainer = TrainerRM(task_pool="dev_tasks")

# 测试环境
test_trainer = TrainerRM(task_pool="test_tasks")

# 生产环境
prod_trainer = TrainerRM(task_pool="prod_tasks")
```

### 2. 清理旧任务

```python
from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017/")
db = client["qlib_tasks"]

# 删除旧的测试任务
db["test_tasks"].delete_many({"status": "done"})

# 或者删除整个集合
db["test_tasks"].drop()
```

### 3. 监控任务

```python
# 检查等待中的任务数量
waiting_count = db["production"].count_documents({"status": "waiting"})
print(f"Waiting tasks: {waiting_count}")

# 检查失败的任务
failed_tasks = db["production"].find({"status": "failed"})
for task in failed_tasks:
    print(f"Failed task: {task['_id']}")
```

---

## 📚 总结

### task_pool 的作用

1. **任务存储**：在 MongoDB 中持久化保存任务
2. **任务隔离**：不同环境使用不同的 pool
3. **任务队列**：Worker 从中获取任务
4. **状态管理**：跟踪任务状态（waiting/running/done）
5. **分布式支持**：多机器共享同一个 pool

### 类比

```
task_pool 就像：
- 餐厅的订单队列
  └─> 每个订单是一个任务
  └─> 厨师从队列中获取订单
  └─> 完成后标记为 "done"

- Jira 的任务列表
  └─> 每个任务有状态
  └─> 可分配给不同的人
  └─> 追踪进度
```

---

## 🎯 快速记忆

```python
# 语法
TrainerRM(task_pool="名称")

# 作用
# 1. 指定 MongoDB 集合名称
# 2. 任务会保存到这个集合
# 3. Worker 从这个集合获取任务
# 4. 实现分布式训练

# 示例
production    ← 实盘交易的任务队列
backtest       ← 回测的任务队列
experiment_A   ← 实验 A 的任务队列
```

---

## 相关文档

- Qlib 官方文档: [Task Management](https://qlib.readthedocs.io/en/latest/task_management.html)
- 项目对比: `docs/TRAINER_COMPARISON.md`
