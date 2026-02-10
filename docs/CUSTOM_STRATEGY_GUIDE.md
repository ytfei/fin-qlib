# 自定义策略和因子集成指南

本指南详细说明如何将自定义策略和新因子集成到 OnlineManager 中。

## 目录

1. [理解架构](#1-理解架构)
2. [自定义策略](#2-自定义策略)
3. [自定义因子（Handler）](#3-自定义因子handler)
4. [配置文件](#4-配置文件)
5. [完整流程](#5-完整流程)
6. [常见问题](#6-常见问题)

---

## 1. 理解架构

### Qlib 的三层架构

```
┌─────────────────────────────────────────────────────────┐
│                    OnlineManager                        │
│  - 管理多个策略                                          │
│  - 执行 routine()                                        │
│  - 生成交易信号                                           │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                   OnlineStrategy                         │
│  - prepare_tasks():    生成训练任务                       │
│  - prepare_online_models(): 选择在线模型                  │
│  - first_tasks():      初始任务                           │
│  - get_collector():    收集结果                           │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                    Task (任务)                            │
│  - model: 模型配置                                         │
│  - dataset: 数据集配置                                     │
│    └─ handler: 因子/特征处理器                             │
└─────────────────────────────────────────────────────────┘
```

### 扩展点

你需要根据情况选择扩展的层次：

| 需求 | 扩展点 | 难度 |
|------|--------|------|
| 使用新因子 | Handler | ⭐ 简单 |
| 修改重训练逻辑 | OnlineStrategy | ⭐⭐ 中等 |
| 完全自定义策略 | OnlineStrategy | ⭐⭐⭐ 较难 |

---

## 2. 自定义策略

### 2.1 何时需要自定义策略？

**使用 RollingStrategy（内置）**：
- ✅ 标准的滚动训练
- ✅ 固定时间间隔重训练

**需要自定义策略**：
- ✅ 固定窗口（不滚动）
- ✅ 自适应重训练（基于性能）
- ✅ 同时保留多个模型
- ✅ 复杂的任务生成逻辑

### 2.2 创建自定义策略

#### 步骤 1: 创建 Python 文件

在 `fin-qlib/` 下创建 `my_strategies/` 目录：

```bash
mkdir -p my_strategies
touch my_strategies/__init__.py
```

#### 步骤 2: 实现策略类

创建 `my_strategies/momentum_strategy.py`:

```python
from typing import List, Dict
from qlib.workflow.online.strategy import OnlineStrategy
from qlib.workflow.online.utils import OnlineToolR
import pandas as pd


class MomentumStrategy(OnlineStrategy):
    """
    动量策略

    逻辑：
    1. 计算市场动量
    2. 动量强时使用激进模型，动量弱时使用保守模型
    """

    def __init__(self, name_id: str,
                 aggressive_task: Dict,
                 conservative_task: Dict,
                 momentum_threshold: float = 0.02):
        super().__init__(name_id=name_id)
        self.aggressive_task = aggressive_task
        self.conservative_task = conservative_task
        self.momentum_threshold = momentum_threshold
        self.tool = OnlineToolR(self.name_id)
        self.current_mode = "conservative"  # or "aggressive"

    def first_tasks(self) -> List[dict]:
        """初始使用保守模型"""
        return [self.conservative_task.copy()]

    def prepare_tasks(self, cur_time, **kwargs) -> List[dict]:
        """根据市场动量切换模型"""
        cur_time = pd.Timestamp(cur_time)

        # 计算市场动量
        momentum = self._calculate_market_momentum(cur_time)

        print(f"Market momentum at {cur_time}: {momentum:.4f}")

        # 根据动量选择模型
        if momentum > self.momentum_threshold:
            # 动量强，使用激进模型
            if self.current_mode != "aggressive":
                print(f"Switching to AGGRESSIVE mode")
                self.current_mode = "aggressive"
            return [self.aggressive_task.copy()]
        else:
            # 动量弱，使用保守模型
            if self.current_mode != "conservative":
                print(f"Switching to CONSERVATIVE mode")
                self.current_mode = "conservative"
            return [self.conservative_task.copy()]

    def _calculate_market_momentum(self, cur_time: pd.Timestamp) -> float:
        """计算市场动量"""
        from qlib.data import D

        # 获取市场指数过去30天的收益率
        index_code = "SH000300"  # 沪深300
        end_date = cur_time
        start_date = cur_time - pd.Timedelta(days=30)

        try:
            df = D.features(
                instruments=[index_code],
                fields=["$close"],
                start_time=start_date,
                end_time=end_date
            )

            if df is not None and len(df) > 0:
                # 计算30日收益率
                momentum = (df.iloc[-1] / df.iloc[0] - 1).values[0]
                return momentum
        except Exception as e:
            print(f"Error calculating momentum: {e}")

        return 0.0

    def get_collector(self, process_list=[], **kwargs):
        from qlib.workflow.task.collect import RecorderCollector
        from qlib.model.ens.group import RollingGroup

        def rec_key(recorder):
            return recorder.info['id']

        return RecorderCollector(
            experiment=self.name_id,
            process_list=process_list or [RollingGroup()],
            rec_key_func=rec_key,
        )
```

### 2.3 在配置中使用

编辑 `config/online_config.yaml`:

```yaml
strategies:
  - name: "Momentum_Strategy"
    enabled: true
    type: "Custom"
    class: "MomentumStrategy"
    module_path: "my_strategies.momentum_strategy"

    init_params:
      momentum_threshold: 0.02  # 2% 动量阈值

    # 定义两个任务模板（激进和保守）
    # 注意：自定义策略如果需要多个模板，需要在代码中处理
    task_template:  # 默认模板（会被代码中的逻辑覆盖）
      model:
        class: "LGBModel"
        module_path: "qlib.contrib.model.gbdt"
      dataset:
        class: "DatasetH"
        module_path: "qlib.data.dataset"
        kwargs:
          handler:
            class: "Alpha158"
            module_path: "qlib.contrib.data.handler"
          segments:
            train: ("2020-01-01", "2022-01-01")
            valid: ("2022-01-01", "2022-07-01")
            test: ("2022-07-01", "2023-01-01")

# 问题：上面的配置只支持一个 task_template
# 如果需要多个模板，修改方案见下文
```

**问题**：配置文件不支持多个 task_template。

**解决方案**：在策略的 `__init__` 中直接定义多个任务：

```python
class MomentumStrategy(OnlineStrategy):
    def __init__(self, name_id: str, task_template: Dict, momentum_threshold: float = 0.02):
        super().__init__(name_id=name_id)
        self.momentum_threshold = momentum_threshold

        # 基于 task_template 创建两个变体
        self.aggressive_task = task_template.copy()
        self.conservative_task = task_template.copy()

        # 修改模型参数
        self.aggressive_task['model']['kwargs'] = {
            'learning_rate': 0.1,  # 激进：高学习率
            'max_depth': 12,        # 更深
        }

        self.conservative_task['model']['kwargs'] = {
            'learning_rate': 0.01,  # 保守：低学习率
            'max_depth': 6,         # 更浅
        }

        # ... 其他代码
```

这样配置文件只需要一个模板：

```yaml
- name: "Momentum_Strategy"
  enabled: true
  type: "Custom"
  class: "MomentumStrategy"
  module_path: "my_strategies.momentum_strategy"

  init_params:
    momentum_threshold: 0.02

  task_template:
    model:
      class: "LGBModel"
      module_path: "qlib.contrib.model.gbdt"
    dataset:
      class: "DatasetH"
      module_path: "qlib.data.dataset"
      kwargs:
        handler:
          class: "Alpha158"
          module_path: "qlib.contrib.data.handler"
        segments:
          train: ("2020-01-01", "2022-01-01")
          valid: ("2022-01-01", "2022-07-01")
          test: ("2022-07-01", "2023-01-01")
```

---

## 3. 自定义因子（Handler）

### 3.1 何时需要自定义 Handler？

**使用内置 Handler（Alpha158, Alpha360 等）**：
- ✅ 使用标准技术指标

**需要自定义 Handler**：
- ✅ 自己研发的因子
- ✅ 特定领域的因子（如基本面、另类数据）
- ✅ 因子组合和筛选

### 3.2 创建自定义 Handler

#### 步骤 1: 创建 Handler 文件

创建 `my_handlers/custom_factors.py`:

```python
from qlib.data.dataset.processor import Processor
import pandas as pd
import numpy as np


class MyCustomHandler(Processor):
    """
    自定义因子处理器

    包含：
    1. 技术指标因子
    2. 市场微观结构因子
    3. 自定义研发因子
    """

    def __init__(self, fit_start_time, fit_end_time, **kwargs):
        super().__init__(fit_start_time=fit_start_time, fit_end_time=fit_end_time)
        print(f"Initializing MyCustomHandler: {fit_start_time} to {fit_end_time}")

    def __call__(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        处理数据，添加自定义因子

        Args:
            df: 原始 OHLCV 数据

        Returns:
            添加了因子的 DataFrame
        """
        print(f"Processing data, shape: {df.shape}")

        # 1. 添加技术指标因子
        df = self._add_technical_factors(df)

        # 2. 添加市场微观结构因子
        df = self._add_microstructure_factors(df)

        # 3. 添加自定义因子
        df = self._add_custom_factors(df)

        print(f"Added factors, final shape: {df.shape}")
        return df

    def _add_technical_factors(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加技术指标因子"""

        # 动量因子
        for window in [5, 10, 20, 60]:
            df[f'return_{window}d'] = df['close'].pct_change(window)

        # 波动率因子
        df['volatility_20d'] = df['close'].pct_change().rolling(20).std()

        # RSI (Relative Strength Index)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi_14'] = 100 - (100 / (1 + rs))

        # MACD
        ema12 = df['close'].ewm(span=12).mean()
        ema26 = df['close'].ewm(span=26).mean()
        df['macd'] = ema12 - ema26

        return df

    def _add_microstructure_factors(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加市场微观结构因子"""

        # 成交量相关
        df['volume_ma5'] = df['volume'].rolling(5).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma5']

        # 价格跳动
        df['price_impact'] = (df['close'] - df['open']) / df['vwap']

        # 买卖压力（基于高低价位置）
        df['buy_pressure'] = (df['close'] - df['low']) / (df['high'] - df['low'] + 1e-6)

        return df

    def _add_custom_factors(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加自定义研发的因子"""

        # 示例：复合动量因子
        df['composite_momentum'] = (
            df['return_5d'] * 0.3 +
            df['return_20d'] * 0.5 +
            df['return_60d'] * 0.2
        )

        # 示例：波动率调整动量
        df['vol_adj_momentum'] = df['composite_momentum'] / (df['volatility_20d'] + 1e-6)

        # 示例：趋势强度
        df['trend_strength'] = df['macd'] * df['rsi_14'] / 100

        return df
```

创建 `my_handlers/__init__.py`:

```python
from .custom_factors import MyCustomHandler

__all__ = ['MyCustomHandler']
```

### 3.2 在配置中使用

编辑 `config/online_config.yaml`:

```yaml
strategies:
  - name: "MyCustom_LGB"
    enabled: true
    type: "RollingStrategy"  # 可以使用内置的 RollingStrategy

    task_template:
      model:
        class: "LGBModel"
        module_path: "qlib.contrib.model.gbdt"
        kwargs:
          loss: "mse"
          learning_rate: 0.0421
          num_leaves: 210

      dataset:
        class: "DatasetH"
        module_path: "qlib.data.dataset"
        kwargs:
          # ===== 关键：使用自定义 Handler =====
          handler:
            class: "MyCustomHandler"
            module_path: "my_handlers.custom_factors"
            # 不需要 init_params，会自动传递 fit_start_time 和 fit_end_time

          segments:
            train: ("2020-01-01", "2022-01-01")
            valid: ("2022-01-01", "2022-07-01")
            test: ("2022-07-01", "2023-01-01")

    rolling_config:
      step: 550
      rtype: "ROLL_SD"
```

---

## 4. 配置文件

### 4.1 配置文件结构

```yaml
strategies:
  - name: "Strategy_Name"        # 唯一标识符
    enabled: true                 # 是否启用
    type: "RollingStrategy"       # 策略类型

    # 如果 type = "RollingStrategy"，使用内置策略
    # 如果 type = "Custom"，需要指定 class 和 module_path

    class: "CustomStrategyClass"  # 仅 type="Custom" 时需要
    module_path: "my_module"      # 仅 type="Custom" 时需要

    init_params:                   # 策略初始化参数
      param1: value1

    task_template:                 # 任务模板
      model:
        class: "ModelClass"
        module_path: "model.module"
        kwargs:
          param1: value1

      dataset:
        class: "DatasetH"
        module_path: "qlib.data.dataset"
        kwargs:
          handler:
            class: "HandlerClass"
            module_path: "handler.module"
            init_params:            # Handler 初始化参数
              handler_param: value
          segments:
            train: ("start", "end")
            valid: ("start", "end")
            test: ("start", "end")

    rolling_config:               # 仅 RollingStrategy 需要
      step: 550
      rtype: "ROLL_SD"
```

### 4.2 内置 vs 自定义

| 配置项 | 内置 RollingStrategy | 自定义 Strategy |
|--------|---------------------|-----------------|
| `type` | `"RollingStrategy"` | `"Custom"` |
| `class` | 不需要 | 必须 |
| `module_path` | 不需要 | 必须 |
| `init_params` | 不需要 | 可选 |
| `task_template` | 必须 | 必须 |
| `rolling_config` | 必须 | 不需要 |

---

## 5. 完整流程

### 5.1 开发自定义因子（推荐新手）

```bash
# 1. 创建 handler
mkdir -p my_handlers
touch my_handlers/__init__.py

# 2. 编辑 my_handlers/custom_factors.py
# （参考上面的代码）

# 3. 测试 handler
python -c "
from my_handlers.custom_factors import MyCustomHandler
print('Handler imported successfully')
"

# 4. 更新配置
# 编辑 config/online_config.yaml，使用新的 handler

# 5. 验证配置
python scripts/test_config.py --config config/online_config.yaml

# 6. 运行
python scripts/run_routine.py --config config/online_config.yaml
```

### 5.2 开发自定义策略

```bash
# 1. 创建策略
mkdir -p my_strategies
touch my_strategies/__init__.py

# 2. 编辑 my_strategies/my_strategy.py
# （实现 OnlineStrategy 接口）

# 3. 测试策略
python -c "
from my_strategies.my_strategy import MyStrategy
print('Strategy imported successfully')
"

# 4. 更新配置
# 使用 type: "Custom"

# 5. 验证和运行
```

### 5.3 完整示例

假设你：
1. 开发了新因子 `MyAlpha`
2. 使用固定窗口训练
3. 每 60 天重训练一次

**步骤 1: 创建 Handler**

`my_handlers/my_alpha.py`:

```python
from qlib.data.dataset.processor import Processor
import pandas as pd

class MyAlpha(Processor):
    def __init__(self, fit_start_time, fit_end_time, **kwargs):
        super().__init__(fit_start_time, fit_end_time)

    def __call__(self, df: pd.DataFrame) -> pd.DataFrame:
        # 你的因子计算逻辑
        df['my_factor'] = df['close'].pct_change(20)
        return df
```

**步骤 2: 创建策略**

`my_strategies/fixed_window.py`:

```python
from qlib.workflow.online.strategy import OnlineStrategy
from qlib.workflow.online.utils import OnlineToolR
import pandas as pd

class FixedWindowRetrain(OnlineStrategy):
    def __init__(self, name_id: str, task_template: dict, interval: int = 60):
        super().__init__(name_id=name_id)
        self.task_template = task_template
        self.interval = interval
        self.tool = OnlineToolR(self.name_id)
        self.last_train = None

    def first_tasks(self):
        return [self.task_template.copy()]

    def prepare_tasks(self, cur_time, **kwargs):
        cur_time = pd.Timestamp(cur_time)

        if self.last_train is None:
            self.last_train = cur_time
            return [self.task_template.copy()]

        if (cur_time - self.last_train).days >= self.interval:
            self.last_train = cur_time
            return [self.task_template.copy()]

        return []

    def get_collector(self, process_list=[], **kwargs):
        from qlib.workflow.task.collect import RecorderCollector
        from qlib.model.ens.group import RollingGroup

        return RecorderCollector(
            experiment=self.name_id,
            process_list=[RollingGroup()],
            rec_key_func=lambda r: r.info['id'],
        )
```

**步骤 3: 配置**

`config/online_config.yaml`:

```yaml
strategies:
  - name: "MyCustom_Strategy"
    enabled: true
    type: "Custom"
    class: "FixedWindowRetrain"
    module_path: "my_strategies.fixed_window"

    init_params:
      interval: 60  # 60天重训练

    task_template:
      model:
        class: "LGBModel"
        module_path: "qlib.contrib.model.gbdt"
      dataset:
        class: "DatasetH"
        module_path: "qlib.data.dataset"
        kwargs:
          handler:
            class: "MyAlpha"
            module_path: "my_handlers.my_alpha"
          segments:
            train: ("2020-01-01", "2023-01-01")  # 固定窗口
            valid: ("2023-01-01", "2023-07-01")
            test: ("2023-07-01", "2024-01-01")
```

---

## 6. 常见问题

### Q1: 模块导入错误

**错误**：
```
ModuleNotFoundError: No module named 'my_strategies'
```

**解决**：
```bash
# 确保 PYTHONPATH 包含项目根目录
export PYTHONPATH=/path/to/fin-qlib:$PYTHONPATH

# 或者修改 managed_manager.py 的导入逻辑
```

### Q2: Handler 参数问题

**错误**：
```
TypeError: __init__() got an unexpected keyword argument
```

**解决**：
```python
# Handler 的 __init__ 必须接受 **kwargs
class MyHandler(Processor):
    def __init__(self, fit_start_time, fit_end_time, **kwargs):
        super().__init__(fit_start_time, fit_end_time)
        # kwargs 中包含配置中的 init_params
        self.param1 = kwargs.get('param1', default_value)
```

### Q3: 数据格式问题

**错误**：
```
KeyError: 'close'
```

**解决**：
```python
# 确保数据包含所需的列
# 可以在 __call__ 开头检查
def __call__(self, df: pd.DataFrame) -> pd.DataFrame:
    required_cols = ['open', 'high', 'low', 'close', 'volume']
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")
    # ... 继续处理
```

### Q4: 如何调试？

```python
# 在 Handler 中添加日志
class MyHandler(Processor):
    def __call__(self, df: pd.DataFrame) -> pd.DataFrame:
        print(f"[DEBUG] Input shape: {df.shape}")
        print(f"[DEBUG] Columns: {df.columns.tolist()}")
        # ... 处理
        print(f"[DEBUG] Output shape: {df_out.shape}")
        return df_out

# 或使用 logging
import logging
logger = logging.getLogger(__name__)

class MyHandler(Processor):
    def __call__(self, df: pd.DataFrame) -> pd.DataFrame:
        logger.info(f"Processing data: {df.shape}")
        # ...
        return df
```

### Q5: 如何使用基本面数据？

```python
class FundamentalHandler(Processor):
    def __call__(self, df: pd.DataFrame) -> pd.DataFrame:
        # 合并基本面数据
        from qlib.data import D

        # 获取 PE, PB 等指标
        fundamentals = D.features(
            df.index.get_level_values('instrument').unique(),
            fields=["$pe", "$pb", "$roe"],
            start_time=df.index.get_level_values('datetime').min(),
            end_time=df.index.get_level_values('datetime').max()
        )

        # 合并
        df = df.join(fundamentals, how='left')

        return df
```

---

## 总结

1. **优先使用内置 Handler**：Alpha158, Alpha360
2. **自定义因子继承 Processor**：实现 `__call__` 方法
3. **简单场景用 RollingStrategy**：配置 `rolling_config`
4. **复杂逻辑自定义 Strategy**：继承 `OnlineStrategy`
5. **逐步测试**：先测试 Handler，再测试 Strategy，最后集成

需要更多示例？查看 `examples/` 目录下的完整代码！
