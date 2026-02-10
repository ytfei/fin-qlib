# 自定义策略和因子 - 快速参考

## 📌 三种常见场景

### 场景 1: 只需要新因子（最常见）

**使用内置 RollingStrategy + 自定义 Handler**

```yaml
strategies:
  - name: "MyFactor_LGB"
    enabled: true
    type: "RollingStrategy"  # ← 使用内置策略

    task_template:
      model:
        class: "LGBModel"
        module_path: "qlib.contrib.model.gbdt"

      dataset:
        class: "DatasetH"
        module_path: "qlib.data.dataset"
        kwargs:
          # ← 只需要修改这里
          handler:
            class: "MyCustomHandler"
            module_path: "my_handlers.custom_factors"
          segments:
            train: ("2020-01-01", "2022-01-01")
            valid: ("2022-01-01", "2022-07-01")
            test: ("2022-07-01", "2023-01-01")

    rolling_config:
      step: 550
      rtype: "ROLL_SD"
```

**Python 代码**：`my_handlers/custom_factors.py`

```python
from qlib.data.dataset.processor import Processor
import pandas as pd

class MyCustomHandler(Processor):
    def __init__(self, fit_start_time, fit_end_time, **kwargs):
        super().__init__(fit_start_time, fit_end_time)

    def __call__(self, df: pd.DataFrame) -> pd.DataFrame:
        # 计算你的因子
        df['my_factor'] = df['close'].pct_change(20)
        return df
```

---

### 场景 2: 需要自定义重训练逻辑

**使用自定义 Strategy**

```yaml
strategies:
  - name: "MyCustom_Strategy"
    enabled: true
    type: "Custom"  # ← 使用自定义策略
    class: "MyCustomStrategy"
    module_path: "my_strategies.my_strategy"

    init_params:
      retrain_interval: 60  # 自定义参数

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
            train: ("2020-01-01", "2023-01-01")  # 固定窗口
            valid: ("2023-01-01", "2023-07-01")
            test: ("2023-07-01", "2024-01-01")
```

**Python 代码**：`my_strategies/my_strategy.py`

```python
from qlib.workflow.online.strategy import OnlineStrategy
from qlib.workflow.online.utils import OnlineToolR
import pandas as pd

class MyCustomStrategy(OnlineStrategy):
    def __init__(self, name_id: str, task_template: dict, retrain_interval: int = 60):
        super().__init__(name_id=name_id)
        self.task_template = task_template
        self.retrain_interval = retrain_interval
        self.tool = OnlineToolR(self.name_id)
        self.last_train = None

    def first_tasks(self):
        return [self.task_template.copy()]

    def prepare_tasks(self, cur_time, **kwargs):
        cur_time = pd.Timestamp(cur_time)

        if self.last_train is None:
            self.last_train = cur_time
            return [self.task_template.copy()]

        # 自定义逻辑：每 N 天重训练
        if (cur_time - self.last_train).days >= self.retrain_interval:
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

---

### 场景 3: 自定义策略 + 自定义因子

**组合使用**

```yaml
strategies:
  - name: "FullCustom_LGB"
    enabled: true
    type: "Custom"
    class: "MyCustomStrategy"
    module_path: "my_strategies.my_strategy"

    init_params:
      retrain_interval: 60

    task_template:
      model:
        class: "LGBModel"
        module_path: "qlib.contrib.model.gbdt"

      dataset:
        class: "DatasetH"
        module_path: "qlib.data.dataset"
        kwargs:
          handler:
            class: "MyCustomHandler"  # ← 自定义 Handler
            module_path: "my_handlers.custom_factors"
          segments:
            train: ("2020-01-01", "2023-01-01")
            valid: ("2023-01-01", "2023-07-01")
            test: ("2023-07-01", "2024-01-01")
```

---

## 🔑 关键代码模板

### Handler 模板

```python
from qlib.data.dataset.processor import Processor
import pandas as pd

class MyCustomHandler(Processor):
    def __init__(self, fit_start_time, fit_end_time, **kwargs):
        """
        Args:
            fit_start_time: 训练开始时间
            fit_end_time: 训练结束时间
            **kwargs: 配置文件中的 init_params
        """
        super().__init__(fit_start_time, fit_end_time)
        self.param1 = kwargs.get('param1', 'default_value')

    def __call__(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        处理数据，添加因子

        Args:
            df: 原始 OHLCV 数据，多层索引 (datetime, instrument)

        Returns:
            添加了因子的 DataFrame
        """
        # 1. 验证输入
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Missing column: {col}")

        # 2. 计算因子
        df['my_factor'] = df['close'].pct_change(20)

        # 3. 返回
        return df
```

### Strategy 模板

```python
from qlib.workflow.online.strategy import OnlineStrategy
from qlib.workflow.online.utils import OnlineToolR
import pandas as pd

class MyCustomStrategy(OnlineStrategy):
    def __init__(self, name_id: str, task_template: dict, **kwargs):
        """
        Args:
            name_id: 策略名称
            task_template: 任务模板
            **kwargs: 配置文件中的 init_params
        """
        super().__init__(name_id=name_id)
        self.task_template = task_template
        self.tool = OnlineToolR(self.name_id)

        # 自定义参数
        self.param1 = kwargs.get('param1', 'default_value')

    def first_tasks(self) -> List[dict]:
        """返回初始任务列表"""
        return [self.task_template.copy()]

    def prepare_tasks(self, cur_time, **kwargs) -> List[dict]:
        """
        根据当前时间，返回需要训练的任务列表

        返回空列表表示不需要重训练
        """
        cur_time = pd.Timestamp(cur_time)

        # 自定义逻辑
        if self._should_retrain(cur_time):
            return [self.task_template.copy()]

        return []

    def _should_retrain(self, cur_time: pd.Timestamp) -> bool:
        """自定义的重训练判断逻辑"""
        # 实现你的逻辑
        return True

    def prepare_online_models(self, trained_models, cur_time=None) -> List:
        """选择在线模型（可选，默认使用所有训练的模型）"""
        if not trained_models:
            return self.tool.online_models()

        self.tool.reset_online_tag(trained_models)
        return trained_models

    def get_collector(self, process_list=[], **kwargs):
        """返回结果收集器"""
        from qlib.workflow.task.collect import RecorderCollector
        from qlib.model.ens.group import RollingGroup

        return RecorderCollector(
            experiment=self.name_id,
            process_list=process_list or [RollingGroup()],
            rec_key_func=lambda r: r.info['id'],
        )
```

---

## 📝 配置检查清单

添加自定义策略/因子时，检查：

- [ ] Python 文件已创建（`my_handlers/` 或 `my_strategies/`）
- [ ] `__init__.py` 文件存在
- [ ] 类可以正常导入（`python -c "from ... import ..."`）
- [ ] 配置文件中 `module_path` 正确
- [ ] 配置文件中 `class` 名称正确
- [ ] 配置文件中 `type` 正确（`RollingStrategy` 或 `Custom`）
- [ ] `init_params` 与 `__init__` 参数匹配
- [ ] 运行 `python scripts/test_config.py --config config/online_config.yaml`

---

## 🚀 快速开始命令

```bash
# 1. 创建目录结构
mkdir -p my_handlers my_strategies
touch my_handlers/__init__.py my_strategies/__init__.py

# 2. 创建 Handler
cat > my_handlers/my_factors.py << 'EOF'
from qlib.data.dataset.processor import Processor
import pandas as pd

class MyFactors(Processor):
    def __init__(self, fit_start_time, fit_end_time, **kwargs):
        super().__init__(fit_start_time, fit_end_time)

    def __call__(self, df: pd.DataFrame) -> pd.DataFrame:
        df['my_factor'] = df['close'].pct_change(20)
        return df
EOF

# 3. 测试导入
python -c "from my_handlers.my_factors import MyFactors; print('OK')"

# 4. 更新配置（编辑 config/online_config.yaml）
# 使用上面的场景 1 配置

# 5. 验证配置
python scripts/test_config.py --config config/online_config.yaml

# 6. 运行
python scripts/first_run.py --config config/online_config.yaml
```

---

## 💡 常见因子示例

```python
# 动量因子
df['momentum_20d'] = df['close'].pct_change(20)

# 波动率
df['volatility'] = df['close'].pct_change().rolling(20).std()

# RSI
delta = df['close'].diff()
gain = delta.where(delta > 0, 0).rolling(14).mean()
loss = -delta.where(delta < 0, 0).rolling(14).mean()
df['rsi'] = 100 - (100 / (1 + gain / loss))

# MACD
ema12 = df['close'].ewm(12).mean()
ema26 = df['close'].ewm(26).mean()
df['macd'] = ema12 - ema26

# 成交量变化
df['volume_change'] = df['volume'].pct_change(5)

# 价格位置
df['price_position'] = (df['close'] - df['low']) / (df['high'] - df['low'])
```

更多示例见：`examples/custom_handler_example.py`
