# Routine 执行过程详解

## 目录
1. [整体流程](#整体流程)
2. [时间管理](#时间管理)
3. [数据管理](#数据管理)
4. [执行步骤详解](#执行步骤详解)
5. [日志补充](#日志补充)

---

## 整体流程

### Routine 的 4 个核心步骤

```
routine() 方法执行流程:
┌─────────────────────────────────────────────────────────────┐
│  1. prepare_tasks()    - 准备训练任务                           │
│  2. trainer.train()     - 训练模型                               │
│  3. prepare_online_models() - 标记在线模型                        │
│  4. prepare_signals()    - 生成交易信号                           │
└─────────────────────────────────────────────────────────────┘
```

### 时间线示意

```
上次训练: 2025-09-26
当前时间: 2026-01-21
滚动步长: 90 天

时间线:
2025-09                    2026-01
  |───────────────────────────|
  ↑
last test
  |
  |<-- 75 天 -->|<- 90 天步长 -->|

实际操作:
- 75 < 90: 不需要新训练
- 更新 3 个在线模型的预测到 2026-01-21
- 收集预测生成信号
```

---

## 时间管理

### 1. 时间来源与设置

```python
# qlib/workflow/online/manager.py:205-207
if cur_time is None:
    cur_time = D.calendar(freq=self.freq).max()  # 获取日历最新日期
self.cur_time = pd.Timestamp(cur_time)
```

**时间优先级**:
1. 用户指定的 `cur_time` 参数
2. 日历中的最大日期

### 2. 关键时间点

| 时间点 | 说明 | 日志位置 |
|--------|------|----------|
| `self.cur_time` | 当前 routine 执行时间 | ✅ 已记录 |
| `last test` | 上次模型的测试开始时间 | ❌ 需补充 |
| `rolling_step` | 滚动步长 | ✅ 已记录 |
| `task test segment` | 每个训练任务的测试期 | ❌ 需补充 |

---

## 数据管理

### 1. 预测数据更新机制

#### update_online_pred() 流程

```
工具类: OnlineToolR (qlib/workflow/online/utils.py)

功能:
  - 为每个在线模型生成最新日期的预测
  - 从 test 期开始预测到最新日期 (cur_time)

输入:
  - cur_time: 2026-01-21
  - 在线模型的 test 期: [2025-09-26, 2025-12-31]

执行:
  - 加载模型
  - 加载 2025-09-26 之后的数据
  - 生成 2025-09-26 ~ 2026-01-21 的预测
  - 追加保存到 pred.pkl

输出:
  - pred.pkl 更新，包含新的预测数据
```

#### 数据文件结构

```python
# pred.pkl 结构
pred.pkl:
  index: (datetime, instrument)  # 多级索引
  values: score                   # 预测得分

示例:
                           score
datetime      instrument
2025-09-26   SH600000        0.5
             SH600001        0.3
             SH600002        0.8
2025-09-27   SH600000        0.6
             SH600001        0.4
...
2026-01-21   SH600000        0.7  ← 最新预测
             SH600001        0.5
```

### 2. 数据流向图

```
┌─────────────────────────────────────────────────────────────┐
│                    数据更新流程                              │
└─────────────────────────────────────────────────────────────┘

1. prepare_tasks() - 判断是否需要新任务
   ├─ 获取上次 test 时间: 2025-09-26
   ├─ 计算时间间隔: 75 天
   ├─ 对比滚动步长: 90 天
   └─ 决策: 75 < 90, 不需要新训练 ✓

2. update_online_pred() - 更新现有模型预测
   ├─ 模型 1: test[2025-09-26, 2025-12-31] → 预测到 2026-01-21
   ├─ 模型 2: test[2025-05-22, 2025-09-25] → 预测到 2026-01-21
   └─ 模型 3: test[2025-01-02, 2025-05-21] → 预测到 2026-01-21

3. get_collector() - 收集预测
   ├─ 从 3 个模型的 pred.pkl 读取
   ├─ 按日期段分组:
   │   ├─ 2025-01-02 ~ 2025-05-21: 模型 3 负责
   │   ├─ 2025-05-22 ~ 2025-09-25: 模型 2 负责
   │   └─ 2025-09-26 ~ 2026-01-21: 模型 1 负责
   └─ 通过 RollingEnsemble 合并

4. prepare_signals() - 生成最终信号
   ├─ 收集 3 个模型的预测
   ├─ 平均集成: pred = (pred1 + pred2 + pred3) / 3
   ├─ 输出: 127,890 个信号
   └─ 覆盖时间: 2025-01-02 ~ 2026-01-21
```

### 3. 滚动模型分配策略

```
时间轴: 2025-01 ~ 2026-01

┌────────────┬────────────┬────────────┬────────────┐
│  模型 3     │  模型 2     │  模型 1     │   新模型    │
├────────────┼────────────┼────────────┼────────────┤
│ 01-02      │ 05-22      │ 09-26      │  待训练      │
│ ~05-21      │ ~09-25      │ ~12-31      │  (未触发)   │
└────────────┴────────────┴────────────┴────────────┘

最新日期: 2026-01-21

模型 1 负责: 09-26 ~ 01-21  ← 主要贡献最新预测
模型 2 负责: 05-22 ~ 09-25  ← 历史参考
模型 3 负责: 01-02 ~ 05-21  ← 历史参考
```

---

## 执行步骤详解

### Step 1: prepare_tasks()

```python
# qlib/workflow/online/strategy.py:167-189
def prepare_tasks(self, cur_time):
    # 1. 获取当前在线模型
    latest_records, max_test = self._list_latest(self.tool.online_models())
    # max_test = 2025-09-26 (上次任务的 test 开始时间)

    # 2. 计算时间间隔
    calendar_latest = transform_end_date(cur_time)  # 2026-01-21
    interval = self.ta.cal_interval(calendar_latest, max_test[0])  # 75 天

    # 3. 判断是否需要新任务
    if interval < self.rg.step:  # 75 < 90
        return []  # 不需要新任务

    # 4. 生成后续任务
    for rec in latest_records:
        task = rec.load_object("task")
        res.extend(self.rg.gen_following_tasks(task, calendar_latest))

    return res  # 返回新任务列表
```

**日志输出**:
```
[INFO] The interval between current time 2026-01-21 and
      last rolling test begin time 2025-09-26 is 75,
      the rolling step is 90
```

**决策逻辑**:
```
if interval >= rolling_step:
    需要新训练 → 生成新任务
else:
    不需要训练 → 返回空列表
```

### Step 2: trainer.train()

```python
# qlib/workflow/online/manager.py:214
models = self.trainer.train(tasks, experiment_name=strategy.name_id)
```

**本例中**: tasks = [] (空列表)，因为 75 < 90

**结果**: 不训练新模型

### Step 3: prepare_online_models()

```python
# qlib/workflow/online/manager.py:217
online_models = strategy.prepare_online_models(models, **model_kwargs)
```

**功能**:
- 将新训练的模型标记为 "online"
- 本例中 models = []，所以只是获取现有在线模型

**在线模型列表**:
```
[
  Recorder(e0b04ee32...),  # 模型 1 - test[2025-09-26, 2025-12-31]
  Recorder(f6d20684...),  # 模型 2 - test[2025-05-22, 2025-09-25]
  Recorder(1848ff56...)   # 模型 3 - test[2025-01-02, 2025-05-21]
]
```

### Step 4: update_online_pred()

```python
# qlib/workflow/online/manager.py:223
strategy.tool.update_online_pred()
```

**功能**: 更新在线模型的预测到当前时间

**执行流程** (针对每个模型):

```python
# 模型 1 示例:
recorder = e0b04ee32...
model = recorder.load_object('model')

# 检查预测数据的最新日期
pred = recorder.load_object('pred.pkl')
latest_date = pred.index.get_level_values('datetime').max()
# latest_date = 2025-12-31

# 目标日期
target_date = cur_time  # 2026-01-21

# 如果需要更新
if latest_date < target_date:
    # 加载最新数据: 2025-12-31 ~ 2026-01-21
    new_data = loader.load(target_date)

    # 生成新预测
    new_pred = model.predict(new_data)

    # 追加保存
    pred = pd.concat([pred, new_pred])
    recorder.save_objects(pred=pred)
```

**日志输出**:
```
[INFO] The data in e0b04ee32... are latest (2026-01-21). No need to update.
[WARNING] The given `to_date`(2026-01-21) is later than `latest_date`(2026-01-21).
```

### Step 5: prepare_signals()

```python
# qlib/workflow/online/manager.py:228
self.prepare_signals(**signal_kwargs)
```

**执行流程**:

```python
# 1. 获取收集器
collector = self.get_collector()
# → MergeCollector 包含 3 个策略的收集器

# 2. 收集预测
predictions = collector()
# → {
#     ('LGB_Alpha158', 'pred'): {
#         (Timestamp('2025-09-26'), Timestamp('2026-02-10')): pred_df_1,
#         (Timestamp('2025-05-22'), Timestamp('2025-09-25')): pred_df_2,
#         (Timestamp('2025-01-02'), Timestamp('2025-05-21')): pred_df_3,
#     }
#   }

# 3. 集成方法 (默认平均)
signals = AverageEnsemble()(predictions)

# 4. 输出信号
# → 127,890 个信号
# → 时间范围: 2025-01-02 ~ 2026-01-21
```

---

## 日志补充

需要补充的关键日志:

### 1. prepare_tasks 日志增强

```python
# 在 qlib/workflow/online/strategy.py:167-189
def prepare_tasks(self, cur_time):
    # 现有日志
    self.logger.info(f"The interval between current time {calendar_latest} and "
                      f"last rolling test begin time {max_test[0]} is {interval}, "
                      f"the rolling step is {self.rg.step}")

    # 需要补充的日志
    self.logger.info(f"[PREPARE_TASKS] Current time: {calendar_latest}")
    self.logger.info(f"[PREPARE_TASKS] Last test begin: {max_test[0]}")
    self.logger.info(f"[PREPARE_TASKS] Time interval: {interval} days")
    self.logger.info(f"[PREPARE_TASKS] Rolling step: {self.rg.step} days")

    if interval < self.rg.step:
        self.logger.info(f"[PREPARE_TASKS] Interval < step, no new tasks needed")
        self.logger.info(f"[PREPARE_TASKS] Next training will be required at: "
                          f"{max_test[0] + pd.Timedelta(days=self.rg.step)}")
    else:
        task_count = len(res)
        self.logger.info(f"[PREPARE_TASKS] Generated {task_count} new tasks")
```

### 2. update_online_pred 日志增强

```python
# 在 qlib/workflow/online/utils.py:159-178
def update_online_pred(self, to_date=None, ...):
    for rec in online_models:
        # 现有日志
        self.logger.warn(f"An exception `{str(e)}` happened when load `pred.pkl`...")

        # 需要补充的日志
        try:
            pred = rec.load_object("pred.pkl")
            latest_date = pred.index.get_level_values("datetime").max()
            target_date = to_date if to_date else D.calendar(freq=self.freq).max()

            self.logger.info(f"[UPDATE_PRED] Model {rec.info['id'][:8]}...")
            self.logger.info(f"[UPDATE_PRED]   Current pred latest: {latest_date}")
            self.logger.info(f"[UPDATE_PRED]   Target date: {target_date}")

            if latest_date >= target_date:
                self.logger.info(f"[UPDATE_PRED]   Predictions are up-to-date, skipping")
            else:
                self.logger.info(f"[UPDATE_PRED]   Updating predictions from {latest_date} to {target_date}")
                # ... 执行更新
                new_latest = new_pred.index.get_level_values("datetime").max()
                self.logger.info(f"[UPDATE_PRED]   Updated, new latest: {new_latest}")

        except Exception as e:
            self.logger.error(f"[UPDATE_PRED] Failed to update model {rec.info['id'][:8]}: {e}")
```

### 3. prepare_signals 日志增强

```python
# 在 qlib/workflow/online/manager.py:258-287
def prepare_signals(self, prepare_func=..., over_write=False):
    # 需要补充的日志
    self.logger.info(f"[PREPARE_SIGNALS] Starting signal preparation")
    self.logger.info(f"[PREPARE_SIGNALS] Current time: {self.cur_time}")
    self.logger.info(f"[PREPARE_SIGNALS] Ensemble method: {type(prepare_func).__name__}")

    # 收集预测
    collector = self.get_collector()
    predictions = collector()

    # 记录收集到的预测信息
    total_preds = 0
    for strat_name, strat_preds in predictions.items():
        pred_count = len(strat_preds)
        total_preds += pred_count

        # 获取时间范围
        all_dates = []
        for key, pred in strat_preds.items():
            dates = pred.index.get_level_values('datetime').unique()
            all_dates.extend(dates)

        if all_dates:
            min_date = min(all_dates)
            max_date = max(all_dates)
            self.logger.info(f"[PREPARE_SIGNALS] Strategy: {strat_name}")
            self.logger.info(f"[PREPARE_SIGNALS]   Predictions: {pred_count}")
            self.logger.info(f"[PREPARE_SIGNALS]   Date range: {min_date} ~ {max_date}")

    self.logger.info(f"[PREPARE_SIGNALS] Total predictions collected: {total_preds}")

    # 生成信号
    signals = prepare_func(predictions)

    # 记录最终信号信息
    self.logger.info(f"[PREPARE_SIGNALS] Generated signals: {len(signals)}")
    if isinstance(signals, pd.DataFrame):
        signal_count = len(signals)
    elif isinstance(signals, pd.Series):
        signal_count = len(signals)

    if len(signals) > 0:
        date_range = signals.index.get_level_values('datetime')
        min_date = date_range.min()
        max_date = date_range.max()
        stock_count = signals.index.get_level_values('instrument').nunique()

        self.logger.info(f"[PREPARE_SIGNALS] Signal date range: {min_date} to {max_date}")
        self.logger.info(f"[PREPARE_SIGNALS] Number of stocks: {stock_count}")

    self.logger.info(f"[PREPARE_SIGNALS] Signal preparation completed")
```

### 4. ManagedOnlineManager 日志增强

```python
# 在 fin-qlib/fqlib/managed_manager.py:510 附近
def run_routine(self, ...):
    # 需要补充的日志
    self.logger.info("=" * 80)
    self.logger.info("ROUTINE TIME MANAGEMENT")
    self.logger.info("=" * 80)
    self.logger.info(f"[ROUTINE] Current routine time: {self.manager.cur_time}")

    # 显示当前在线模型信息
    for strategy in self.manager.strategies:
        online_models = strategy.tool.online_models()
        self.logger.info(f"[ROUTINE] Strategy: {strategy.name_id}")
        self.logger.info(f"[ROUTINE]   Online models: {len(online_models)}")

        # 显示每个模型的时间范围
        for i, rec in enumerate(online_models):
            try:
                task = rec.load_object("task")
                test_seg = task["dataset"]["kwargs"]["segments"]["test"]
                self.logger.info(f"[ROUTINE]     Model {i}: test {test_seg}")
            except:
                self.logger.info(f"[ROUTINE]     Model {i}: (无法读取任务配置)")

    self.logger.info("=" * 80)
```

---

## 数据正确性保证

### 1. 时间切片机制

Qlib 使用时间切片来管理不同时间段的预测：

```python
# RollingEnsemble (qlib/model/ensemble.py)
# 自动识别预测的时间范围，并分配给对应模型

# 模型时间覆盖:
# 模型 1: test[2025-09-26, 2025-12-31] → 负责 09-26 ~ 12-31
# 模型 2: test[2025-05-22, 2025-09-25] → 负责 05-22 ~ 09-25
# 模型 3: test[2025-01-02, 2025-05-21] → 负责 01-02 ~ 05-21

# 对于 2026-01-21 的请求:
# → 使用模型 1 的预测（因为它覆盖到最新日期）
```

### 2. 预测合并策略

```
时间点: 2026-01-15
股票: SH600000

可用预测:
- 模型 1: 有预测 (test 覆盖到 2025-12-31，需要扩展)
- 模型 2: 无预测 (test 期在 2025-09-25 就结束了)
- 模型 3: 无预测 (test 期在 2025-05-21 就结束了)

实际操作:
1. update_online_pred() 扩展模型 1 的预测到 2026-01-21
2. RollingEnsemble 使用模型 1 的预测
3. 其他模型在历史时间段提供参考
```

### 3. 最新数据保证

```python
# 数据更新检查机制
def ensure_latest_data():
    # 1. 检查数据源最新日期
    calendar_latest = D.calendar(freq='day').max()
    # 2026-01-21

    # 2. 对比预测数据最新日期
    pred_latest = pred.index.get_level_values('datetime').max()
    # 2025-12-31

    # 3. 如果存在差距，更新预测
    if calendar_latest > pred_latest:
        # 加载 calendar_latest 之前的数据
        # 生成新预测到 calendar_latest
        update_predictions()
```

### 4. 每日执行 routine 的数据流

```
Day 1: 2026-01-01
  ├─ 上次模型 test: 2025-09-26
  ├─ cur_time: 2026-01-01
  ├─ interval: 96 天 > 90 天
  ├─ 训练新模型 ✓
  ├─ 更新预测到 2026-01-01
  └─ 生成信号

Day 2: 2026-01-02
  ├─ 上次模型 test: 2025-12-27 (Day 1 训练的)
  ├─ cur_time: 2026-01-02
  ├─ interval: 6 天 < 90 天
  ├─ 不训练新模型
  ├─ 扩展模型 1 预测 1 天
  └─ 生成信号

Day 3: 2026-01-03
  ├─ 上次模型 test: 2025-12-27
  ├─ cur_time: 2026-01-03
  ├─ interval: 7 天 < 90 天
  ├─ 不训练新模型
  ├─ 扩展模型 1 预测 1 天
  └─ 生成信号

... 直到 Day 90: 2026-03-27
  ├─ 上次模型 test: 2025-12-27
  ├─ cur_time: 2026-03-27
  ├─ interval: 90 天 >= 90 天
  ├─ 训练新模型 ✓
  └─ ...
```

---

## 总结：如何确保每天使用正确、最新数据

### ✅ Qlib 已有的机制

1. **自动时间管理**
   - cur_time 自动获取日历最新日期
   - 无需手动指定

2. **智能预测更新**
   - update_online_pred() 自动检测需要更新的日期范围
   - 只加载需要的新数据
   - 追加保存，不覆盖历史预测

3. **时间切片模型分配**
   - RollingEnsemble 自动选择覆盖当前时间段的模型
   - 每个模型负责其 test 期的时间范围

4. **滑动窗口机制**
   - 每隔 rolling_step 天重新训练
   - 使用最新的训练数据（2年滚动窗口）

### 📋 每日 routine 检查清单

运行 routine 时，系统自动检查：

```
□ 1. 时间检查
     └─ cur_time 是最新交易日期？
     └─ 距上次训练是否 >= rolling_step 天？

□ 2. 任务生成
     └─ 需要新训练 → 生成任务
     └─ 不需要 → 跳过

□ 3. 预测更新
     └─ 检查每个在线模型的 pred.pkl 最新日期
     └─ 如果 < cur_time → 加载新数据并扩展预测

□ 4. 信号收集
     └─ 从多个模型收集预测
     └─ 使用 RollingEnsemble 按时间分配
     └─ 集成生成最终信号

□ 5. 信号输出
     └─ 保存到 signals/signals_YYYYMMDD.csv
     └─ 更新 signals_latest.csv
```

### 🔍 验证数据正确性的方法

```python
# 方法 1: 检查信号日期范围
signals = manager.get_signals()
print(f"信号时间范围: {signals.index.get_level_values('datetime').min()} "
      f"to {signals.index.get_level_values('datetime').max()}")

# 方法 2: 检查在线模型预测
for strategy in manager.strategies:
    models = strategy.tool.online_models()
    for rec in models:
        pred = rec.load_object('pred.pkl')
        latest = pred.index.get_level_values('datetime').max()
        print(f"模型 {rec.info['id'][:8]}... 预测最新日期: {latest}")

# 方法 3: 检查任务配置
for strategy in manager.strategies:
    models = strategy.tool.online_models()
    for rec in models:
        task = rec.load_object('task')
        test = task["dataset"]["kwargs"]["segments"]["test"]
        print(f"模型负责时间段: {test}")
```

---

## 执行时间估算

从日志可以看到：

```
总耗时: ~54 秒
├─ Loading artifacts: ~2 秒
├─ prepare_tasks: < 0.1 秒
├─ 训练: 0 秒 (无新任务)
├─ prepare_online_models: < 0.1 秒
├─ update_online_pred: ~26 秒 (3个模型)
├─ prepare_signals: ~0.5 秒
└─ 保存 checkpoint: < 0.1 秒
```

**瓶颈**: update_online_pred() 加载数据和预测

---

## 需要补充的日志

基于以上分析，需要在以下位置补充日志：

1. ✅ prepare_tasks - 时间计算和任务决策
2. ✅ update_online_pred - 预测更新过程
3. ✅ prepare_signals - 信号生成过程
4. ✅ run_routine - 时间管理概览

这些日志补充将帮助追踪：
- 何时需要训练新模型
- 预测数据的时间范围
- 信号的日期覆盖
- 数据更新的具体操作
