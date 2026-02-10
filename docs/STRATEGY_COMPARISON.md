# RollingStrategy vs 自定义策略 - 对比分析

## 核心区别

| 维度 | RollingStrategy | 自定义策略 |
|------|-----------------|-----------|
| **触发机制** | 时间驱动（固定间隔） | 自定义（性能、事件等） |
| **使用难度** | ⭐ 简单 | ⭐⭐⭐ 复杂 |
| **代码量** | 配置即可 | 需要编写代码 |
| **灵活性** | 低 | 高 |
| **适用场景** | 标准生产环境 | 特殊需求 |

---

## 场景对比

### 场景 1: 每2年重训练

**使用 RollingStrategy**：

```yaml
# 配置即可，无需写代码
strategies:
  - name: "Standard"
    type: "RollingStrategy"
    task_template: {...}
    rolling_config:
      step: 550  # 每2年
      rtype: "ROLL_SD"
```

**使用自定义策略**：

```python
# 需要写几十行代码
class MyStrategy(OnlineStrategy):
    def prepare_tasks(self, cur_time, **kwargs):
        if self._should_retrain(cur_time):  # 手动判断
            return [self.task_template.copy()]
        return []
```

**结论**：简单场景用 RollingStrategy

---

### 场景 2: 性能下降时重训练

**使用 RollingStrategy**：

❌ 不支持！只能按时间重训练

**使用自定义策略**：

```python
class AdaptiveStrategy(OnlineStrategy):
    def prepare_tasks(self, cur_time, **kwargs):
        # 检查性能
        current_ic = self._get_current_performance()

        if current_ic < 0.03:  # IC 低于阈值
            return [self.task_template.copy()]
        return []
```

**结论**：复杂逻辑需要自定义策略

---

## 选择建议

```
你的需求
    │
    ├─ 只是想定期更新模型？
    │   └─> RollingStrategy ✅
    │
    ├─ 需要根据性能动态调整？
    │   └─> 自定义 Strategy ✅
    │
    ├─ 想同时保留多个模型？
    │   └─> 自定义 Strategy ✅
    │
    └─ 刚开始学习？
        └─> RollingStrategy ✅
```

---

## 代码对比

### 使用 RollingStrategy

```python
# 只需配置
strategy = RollingStrategy(
    name_id="my_strategy",
    task_template=task_config,
    rolling_gen=RollingGen(step=550, rtype=ROLL_SD)
)

# 自动处理：
# ✅ 判断何时重训练
# ✅ 生成滚动任务
# ✅ 切换在线模型
```

### 使用自定义策略

```python
# 需要实现多个方法
class MyStrategy(OnlineStrategy):
    def __init__(self, name_id, task_template, retrain_interval):
        self.task_template = task_template
        self.retrain_interval = retrain_interval
        self.tool = OnlineToolR(name_id)
        self.last_train = None

    def first_tasks(self):
        self.last_train = pd.Timestamp.now()
        return [self.task_template.copy()]

    def prepare_tasks(self, cur_time, **kwargs):
        cur_time = pd.Timestamp(cur_time)
        if (cur_time - self.last_train).days >= self.retrain_interval:
            self.last_train = cur_time
            return [self.task_template.copy()]
        return []

    def prepare_online_models(self, trained_models, cur_time=None):
        if trained_models:
            self.tool.reset_online_tag(trained_models)
        return trained_models or self.tool.online_models()

    def get_collector(self, process_list=[], **kwargs):
        # 实现收集器
        ...
```

---

## 总结

| 需求 | 推荐 | 原因 |
|------|------|------|
| 标准滚动训练 | RollingStrategy | 配置简单，开箱即用 |
| 自定义重训练逻辑 | 自定义策略 | 灵活，满足特殊需求 |
| 初学者 | RollingStrategy | 无需编程 |
| 高级用户 | 两者结合 | 基础用 Rolling，特殊逻辑自定义 |
