# RollingStrategy 详解

## 核心概念

`RollingStrategy` 是 Qlib 中用于**滚动训练**的策略类，解决了量化投资中**模型时效性**的核心问题。

---

## 为什么需要 RollingStrategy？

### 问题背景

在量化投资中，市场环境是动态变化的：

```
2020年市场:  特征A有效，特征B无效
2021年市场:  特征A失效，特征B有效
2022年市场:  又是新的规律...
```

如果使用**固定模型**（一次训练，永久使用）：
- ❌ 模型会逐渐失效
- ❌ 无法适应市场变化
- ❌ 预测能力下降

### 解决方案：滚动训练

**定期用新数据重新训练模型**，保持模型的有效性。

```
时间线：
├─ 2020-01-01: 用 [2018-2020] 训练模型1 → 用于预测 2020-H1
├─ 2021-01-01: 用 [2019-2021] 训练模型2 → 用于预测 2021-H1  (替换模型1)
├─ 2022-01-01: 用 [2020-2022] 训练模型3 → 用于预测 2022-H1  (替换模型2)
└─ ...
```

这就是 **RollingStrategy** 做的事情！

---

## RollingStrategy 的工作原理

### 1. 核心机制

```python
class RollingStrategy(OnlineStrategy):
    def __init__(self, name_id, task_template, rolling_gen):
        """
        Args:
            task_template: 任务模板（模型+数据配置）
            rolling_gen: 滚动生成器（控制如何滚动）
        """
```

### 2. 滚动方式

#### 方式 A: 滑动窗口

```
训练窗口大小固定，整体向前移动

Task 1: Train[2018-2020] Test[2020-H1]
Task 2: Train[2019-2021] Test[2021-H1]  ← 向前移动
Task 3: Train[2020-2022] Test[2022-H1]  ← 继续移动

优点: 模型始终使用最新的数据
缺点: 计算量大（每次都要重新训练）
```

#### 方式 B: 扩展窗口

```
训练起点固定，终点向前移动

Task 1: Train[2018-2020] Test[2020-H1]
Task 2: Train[2018-2021] Test[2021-H1]  ← 只扩展终点
Task 3: Train[2018-2022] Test[2022-H1]  ← 继续扩展

优点: 使用了所有历史数据
缺点: 计算量越来越大
```

### 3. 滚动参数

```python
RollingGen(
    step=550,           # 滚动步长（550个交易日 ≈ 2年）
    rtype=RollingGen.ROLL_SD  # ROLL_SD=滑动窗口, ROLL_EX=扩展窗口
)
```

---

## 完整工作流程

### 初始化阶段 (first_train)

```python
# 1. 创建策略
strategy = RollingStrategy(
    name_id="LGB_rolling",
    task_template={...},  # 模型和数据配置
    rolling_gen=RollingGen(step=550, rtype=RollingGen.ROLL_SD)
)

# 2. 首次训练
manager = OnlineManager([strategy])
manager.first_train()
```

**发生了什么？**

```
Step 1: first_tasks()
    └─> 根据 task_template 和 rolling_gen 生成第一个任务
        └─> train: [2020-01-01, 2022-01-01]
            └─> valid: [2022-01-01, 2022-07-01]
            └─> test: [2022-07-01, 2023-01-01]

Step 2: trainer.train()
    └─> 训练模型
    └─> 保存到 Recorder (mlruns://...)

Step 3: prepare_online_models()
    └─> 将新训练的模型标记为 "online"
    └─> 旧的模型标记为 "offline"

结果:
    - 有了第一个模型
    - 这个模型现在是 "online" 状态
    - 用于生成 2022-07-01 到 2023-01-01 的预测
```

---

### 日常更新阶段 (routine)

```python
# 2024-01-15 执行 routine
manager.routine(cur_time="2024-01-15")
```

**发生了什么？**

```
Step 1: prepare_tasks(cur_time="2024-01-15")
    └─> 检查当前在线模型
        └─> 找到最后一个模型的测试段结束时间: 2023-01-01

    └─> 计算距离: 2024-01-15 - 2023-01-01 = 380天

    └─> 判断: 380 < 550 (step)
        └─> 还没到滚动时间
        └─> 返回: []  (不需要训练新模型)

Step 2: trainer.train([])
    └─> 没有任务，跳过训练

Step 3: prepare_online_models([])
    └─> 没有新模型，保持现有模型 online

结果: 模型不更新，继续使用旧模型
```

**如果到了滚动时间会怎样？**

```
假设现在是 2024-07-01 (距离上次训练超过 550 天)

Step 1: prepare_tasks(cur_time="2024-07-01")
    └─> 距离上次测试结束: 550+ 天

    └─> 判断: 550 >= 550 (step)
        └─> 需要滚动！
        └─> 生成新任务:
            └─> train: [2022-01-01, 2024-01-01]  ← 向前滚动2年
            └─> valid: [2024-01-01, 2024-07-01]
            └─> test: [2024-07-01, 2025-01-01]

Step 2: trainer.train([new_task])
    └─> 训练新模型
    └─> 保存到新的 Recorder

Step 3: prepare_online_models([new_model])
    └─> 将旧模型标记为 offline
    └─> 将新模型标记为 online

Step 4: update_online_pred()
    └─> 用新的 online 模型更新预测

结果:
    - 模型切换完成
    - 新模型用于后续预测
```

---

## 图解说明

### 时间线图

```
时间轴:    2020──────2022──────2024──────2026
           │         │         │         │

模型1:      [===Train===][===Test===]
                           ↑
                      在线期间 (2022-2024)

模型2:                [===Train===][===Test===]
                                        ↑
                                   在线期间 (2024-2026)

滚动间隔: 约2年 (550个交易日)
```

### 模型切换图

```
2022-07-01 ─────────────────────────────────────►
            │                                    │
            │  模型1 (online)                      │
            │  ├─ 训练: 2020-2022                 │
            │  └─ 预测: 2022-07-01 到 2024-06-30    │
            │                                    │
2024-07-01 ─────────────────────────────────────►
            │                                    │
            │  模型2 (online) ← 切换！             │
            │  ├─ 训练: 2022-2024                 │
            │  └─ 预测: 2024-07-01 到 2026-06-30    │
            │                                    │
            │  模型1 (offline)                    │
```

---

## 关键方法详解

### 1. first_tasks()

```python
def first_tasks(self) -> List[dict]:
    """
    生成初始任务

    Returns:
        [task1, task2, ...]  # 通常只有一个
    """
    return task_generator(
        tasks=self.task_template,      # 任务模板
        generators=self.rg,             # RollingGen
    )
```

**作用**：系统初始化时调用，生成第一批训练任务。

---

### 2. prepare_tasks(cur_time)

```python
def prepare_tasks(self, cur_time) -> List[dict]:
    """
    根据当前时间，判断是否需要生成新的训练任务

    Args:
        cur_time: 当前时间 (如 "2024-01-15")

    Returns:
        []  # 不需要训练
        或
        [new_task]  # 需要训练新任务
    """
    # 1. 获取当前在线模型
    online_models = self.tool.online_models()

    # 2. 找到最后一个模型的测试段结束时间
    latest_test_end = find_latest_test_end(online_models)

    # 3. 计算时间间隔
    days_diff = (cur_time - latest_test_end).days

    # 4. 判断是否需要滚动
    if days_diff >= self.rg.step:
        # 生成新的滚动任务
        return generate_following_tasks(
            base_task,
            cur_time
        )
    else:
        # 还没到滚动时间
        return []
```

**作用**：routine 时调用，自动判断是否需要重训练。

---

### 3. prepare_online_models(trained_models)

```python
def prepare_online_models(self, trained_models, cur_time=None):
    """
    从训练好的模型中选择在线模型

    Args:
        trained_models: 刚训练完的模型列表

    Returns:
        当前应该是 online 的模型列表
    """
    if not trained_models:
        # 没有新模型，保持现状
        return self.tool.online_models()

    # 默认实现：将所有新训练的模型设为 online
    # 将旧模型设为 offline
    self.tool.reset_online_tag(trained_models)

    return trained_models
```

**作用**：切换在线模型。

**默认行为**：新模型替换旧模型（只保留最新的）

**自定义行为**：可以保留多个模型在线（如集成策略）

---

## 使用场景

### 场景 1: 标准滚动训练

```python
# 每2年重新训练一次
strategy = RollingStrategy(
    name_id="LGB_standard",
    task_template={...},  # 标准配置
    rolling_gen=RollingGen(
        step=550,         # 550天 ≈ 2年
        rtype=RollingGen.ROLL_SD  # 滑动窗口
    )
)
```

### 场景 2: 快速滚动（高频更新）

```python
# 每6个月重新训练一次
strategy = RollingStrategy(
    name_id="LGB_fast",
    task_template={...},
    rolling_gen=RollingGen(
        step=130,         # 130天 ≈ 6个月
        rtype=RollingGen.ROLL_SD
    )
)
```

### 场景 3: 扩展窗口（保留更多历史）

```python
# 使用扩展窗口，保留所有历史数据
strategy = RollingStrategy(
    name_id="LGB_expanding",
    task_template={...},
    rolling_gen=RollingGen(
        step=550,
        rtype=RollingGen.ROLL_EX  # 扩展窗口
    )
)
```

---

## 配置示例

### 完整配置

```yaml
strategies:
  - name: "LGB_Alpha158_Rolling"
    enabled: true
    type: "RollingStrategy"  # ← 使用 RollingStrategy

    task_template:
      model:
        class: "LGBModel"
        module_path: "qlib.contrib.model.gbdt"
        kwargs:
          loss: "mse"
          learning_rate: 0.0421

      dataset:
        class: "DatasetH"
        module_path: "qlib.data.dataset"
        kwargs:
          handler:
            class: "Alpha158"
            module_path: "qlib.contrib.data.handler"

          # 数据段配置
          segments:
            train: ("2020-01-01", "2022-01-01")  # 训练集
            valid: ("2022-01-01", "2022-07-01")  # 验证集
            test: ("2022-07-01", "2023-01-01")    # 测试集

    # 滚动配置（关键！）
    rolling_config:
      step: 550         # 每550天滚动一次
      rtype: "ROLL_SD"  # 滑动窗口
```

### 数据段含义

```python
segments:
    train: ("2020-01-01", "2022-01-01")
        # 用于训练模型的数据
        # 模型通过这些数据学习规律

    valid: ("2022-01-01", "2022-07-01")
        # 用于验证模型的数据
        # 在训练过程中用于早停、调参

    test: ("2022-07-01", "2023-01-01")
        # 测试数据（out-of-sample）
        # 评估模型的泛化能力
        # 这个时间段在未来，用于实战预测
```

---

## 关键参数

### step（滚动步长）

```python
step=550  # 550个交易日 ≈ 2年

选择标准:
- 太短 (如30天):  模型更新频繁，计算成本高
- 太长 (如1000天): 模型可能过时，适应性差

常见选择:
- 130天  ≈ 6个月  (快速更新)
- 550天  ≈ 2年    (标准)
- 780天  ≈ 3年    (慢速更新)
```

### rtype（滚动类型）

```python
# ROLL_SD: Sliding Window（滑动窗口）
优点: 模型始终使用最新数据
缺点: 丢弃了早期数据

# ROLL_EX: Expanding Window（扩展窗口）
优点: 保留了所有历史数据
缺点: 计算成本随时间增加
```

---

## 与其他策略对比

### RollingStrategy vs FixedWindowStrategy

| 特性 | RollingStrategy | FixedWindowStrategy |
|------|-----------------|---------------------|
| 训练数据 | 始终向前滚动 | 固定时间段 |
| 适应市场变化 | ✅ 好 | ⚠️ 较差 |
| 计算成本 | 高 | 低 |
| 适用场景 | 生产环境 | 研究阶段 |

### RollingStrategy vs AdaptiveStrategy

| 特性 | RollingStrategy | AdaptiveStrategy |
|------|-----------------|-----------------|
| 触发条件 | 时间驱动 | 性能驱动 |
| 训练频率 | 固定 | 动态 |
| 复杂度 | 低 | 高 |

---

## 实际运行示例

### 假设配置

```python
RollingGen(step=550, rtype=ROLL_SD)  # 每2年滚动
```

### 运行时间线

```
2024-01-01 (初始化)
├─ first_train()
│   ├─ 生成任务1: train[2020-2022], test[2022-2023]
│   ├─ 训练模型1
│   └─ 模型1 设为 online
│
2024-01-15 (routine, 距上次 14 天)
├─ prepare_tasks("2024-01-15")
│   ├─ 检查: 14 < 550
│   └─ 返回 []  # 不需要训练
│
2024-07-01 (routine, 距上次 548 天)
├─ prepare_tasks("2024-07-01")
│   ├─ 检查: 548 < 550
│   └─ 返回 []  # 还不需要
│
2024-07-02 (routine, 距上次 549 天)
├─ prepare_tasks("2024-07-02")
│   ├─ 检查: 549 < 550
│   └─ 返回 []  # 还不需要
│
2024-07-03 (routine, 距上次 550 天)
├─ prepare_tasks("2024-07-03")
│   ├─ 检查: 550 >= 550  ✅
│   ├─ 生成任务2: train[2022-2024], test[2024-2025]
│   ├─ 训练模型2
│   ├─ 模型2 设为 online
│   └─ 模型1 设为 offline
│
... 继续使用模型2，直到下次滚动
```

---

## 总结

### RollingStrategy 的核心价值

1. **自动重训练**：定期自动用新数据训练模型
2. **模型切换**：自动切换到新模型
3. **配置简单**：只需配置 step 和 rtype
4. **生产就绪**：适用于实盘交易系统

### 适用场景

✅ **适合使用 RollingStrategy**：
- 生产环境在线交易
- 需要定期更新模型
- 市场环境持续变化
- 有充足的计算资源

❌ **不适合使用 RollingStrategy**：
- 一次性研究分析
- 计算资源有限
- 市场环境稳定

### 下一步

- 如果只是简单滚动，使用 `RollingStrategy`
- 如果需要自定义触发逻辑，使用自定义 `OnlineStrategy`
- 参考 `docs/QUICK_REFERENCE.md` 了解如何自定义
