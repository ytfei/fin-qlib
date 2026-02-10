# 添加自定义策略和因子 - 完整指南

## 📚 相关文档

本项目提供了三层文档，帮助你添加自定义策略和因子：

| 文档 | 用途 | 何时阅读 |
|------|------|---------|
| **QUICK_REFERENCE.md** | 快速参考，3种常见场景 | 快速上手 |
| **CUSTOM_STRATEGY_GUIDE.md** | 详细教程，包含完整示例 | 深入学习 |
| **examples/** | 可运行的示例代码 | 参考实现 |

---

## 🎯 我该用什么？

### 场景判断

```
你的需求
    │
    ├─ 只想添加新因子/特征？
    │   └─> 使用 RollingStrategy + 自定义 Handler
    │       参考：docs/QUICK_REFERENCE.md 场景1
    │
    ├─ 想改变重训练逻辑（如固定窗口）？
    │   └─> 使用自定义 Strategy
    │       参考：docs/QUICK_REFERENCE.md 场景2
    │
    └─ 两者都要？
        └─> 自定义 Strategy + 自定义 Handler
            参考：docs/QUICK_REFERENCE.md 场景3
```

---

## 🚀 5分钟快速添加（最常见场景）

### 假设：你开发了新因子，想用 RollingStrategy

**步骤 1: 创建 Handler**

```bash
cd fin-qlib

# 创建目录
mkdir -p my_handlers
touch my_handlers/__init__.py

# 创建文件
cat > my_handlers/my_factors.py << 'EOF'
from qlib.data.dataset.processor import Processor
import pandas as pd

class MyFactors(Processor):
    def __init__(self, fit_start_time, fit_end_time, **kwargs):
        super().__init__(fit_start_time, fit_end_time)

    def __call__(self, df: pd.DataFrame) -> pd.DataFrame:
        # 在这里添加你的因子计算逻辑
        df['my_momentum'] = df['close'].pct_change(20)
        df['my_volatility'] = df['close'].pct_change().rolling(20).std()
        return df
EOF

# 测试导入
python -c "from my_handlers.my_factors import MyFactors; print('✓ Handler 导入成功')"
```

**步骤 2: 更新配置**

编辑 `config/online_config.yaml`:

```yaml
strategies:
  - name: "MyStrategy"
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
          # ← 只需修改这里
          handler:
            class: "MyFactors"  # 你的 Handler 类名
            module_path: "my_handlers.my_factors"  # 模块路径
          segments:
            train: ("2020-01-01", "2022-01-01")
            valid: ("2022-01-01", "2022-07-01")
            test: ("2022-07-01", "2023-01-01")

    rolling_config:
      step: 550
      rtype: "ROLL_SD"
```

**步骤 3: 验证和运行**

```bash
# 验证配置
python scripts/test_config.py --config config/online_config.yaml

# 运行
python scripts/run_routine.py --config config/online_config.yaml
```

---

## 📖 完整示例文件

### 示例 1: 自定义 Handler

文件：`examples/custom_handler_example.py`

包含：
- `MultiStyleFactorHandler` - 多风格因子（动量、反转、波动率）
- `Alpha360Custom` - 自定义 Alpha360
- 完整的因子计算示例

### 示例 2: 自定义 Strategy

文件：`examples/custom_strategy_example.py`

包含：
- `FixedWindowStrategy` - 固定窗口策略
- `EnsembleStrategy` - 集成策略（保留多个模型）
- `AdaptiveRetrainStrategy` - 自适应重训练

### 示例 3: 配置文件

文件：`config/online_config_custom.yaml`

展示：
- 如何配置自定义策略
- 如何配置自定义 Handler
- `init_params` 的使用
- 多种策略配置示例

---

## 🔍 配置文件关键区别

### 内置 RollingStrategy

```yaml
- name: "Strategy"
  type: "RollingStrategy"  # ← 内置
  # 不需要 class 和 module_path

  rolling_config:          # ← 需要这个
    step: 550
    rtype: "ROLL_SD"
```

### 自定义 Strategy

```yaml
- name: "Strategy"
  type: "Custom"           # ← 自定义
  class: "MyStrategy"      # ← 必需
  module_path: "my_module" # ← 必需

  init_params:             # ← 可选
    param: value

  # 不需要 rolling_config
```

### 自定义 Handler（两种策略都可以用）

```yaml
task_template:
  dataset:
    kwargs:
      handler:
        class: "MyHandler"        # ← 你的 Handler 类名
        module_path: "my_handlers" # ← 模块路径
        init_params:               # ← Handler 参数（可选）
          window: 20
```

---

## 📝 实现检查清单

### Handler 实现

- [ ] 继承 `Processor`
- [ ] 实现 `__init__(self, fit_start_time, fit_end_time, **kwargs)`
- [ ] 实现 `__call__(self, df: pd.DataFrame) -> pd.DataFrame`
- [ ] `__call__` 返回添加了因子的 DataFrame
- [ ] 创建 `__init__.py` 文件
- [ ] 测试导入成功

### Strategy 实现

- [ ] 继承 `OnlineStrategy`
- [ ] 实现 `__init__(self, name_id: str, ...)`
- [ ] 实现 `first_tasks(self) -> List[dict]`
- [ ] 实现 `prepare_tasks(self, cur_time, **kwargs) -> List[dict]`
- [ ] 实现 `get_collector(self, ...) -> Collector`
- [ ] 可选：实现 `prepare_online_models(self, trained_models, ...)`
- [ ] 创建 `__init__.py` 文件
- [ ] 测试导入成功

### 配置文件

- [ ] `name` 唯一
- [ ] `enabled: true` 或 `false`
- [ ] `type` 正确（`RollingStrategy` 或 `Custom`）
- [ ] 自定义策略时有 `class` 和 `module_path`
- [ ] `task_template` 完整
- [ ] `module_path` 可以正确导入
- [ ] 运行 `test_config.py` 验证

---

## 🐛 调试技巧

### 1. 验证导入

```bash
# 测试 Handler
python -c "from my_handlers.my_factors import MyFactors; print('OK')"

# 测试 Strategy
python -c "from my_strategies.my_strategy import MyStrategy; print('OK')"
```

### 2. 验证配置

```bash
python scripts/test_config.py --config config/online_config.yaml
```

### 3. 添加调试输出

```python
class MyHandler(Processor):
    def __call__(self, df: pd.DataFrame) -> pd.DataFrame:
        print(f"[DEBUG] Input: {df.shape}")
        # ... 处理
        print(f"[DEBUG] Output: {df_out.shape}")
        return df_out
```

### 4. 查看日志

```bash
tail -f logs/online_manager_*.log
```

---

## 📂 项目结构

```
fin-qlib/
├── docs/                              # 📚 文档
│   ├── QUICK_REFERENCE.md             # 快速参考（推荐！）
│   └── CUSTOM_STRATEGY_GUIDE.md       # 详细教程
│
├── examples/                          # 💡 示例代码
│   ├── custom_handler_example.py      # Handler 示例
│   └── custom_strategy_example.py     # Strategy 示例
│
├── my_handlers/                       # 👤 你的 Handler（新建）
│   ├── __init__.py
│   └── my_factors.py
│
├── my_strategies/                     # 👤 你的 Strategy（新建）
│   ├── __init__.py
│   └── my_strategy.py
│
└── config/                            # ⚙️ 配置
    ├── online_config_custom.yaml      # 自定义示例配置
    └── online_config.yaml             # 你的配置
```

---

## 🎓 学习路径

### 初学者（第一次添加）

1. 阅读 `docs/QUICK_REFERENCE.md` 场景 1
2. 参考示例创建简单的 Handler
3. 使用内置 `RollingStrategy`
4. 测试运行

### 进阶者（自定义逻辑）

1. 阅读 `docs/QUICK_REFERENCE.md` 场景 2
2. 参考 `examples/custom_strategy_example.py`
3. 实现自定义 `OnlineStrategy`
4. 结合自定义 Handler

### 高级用户（完全定制）

1. 阅读 `docs/CUSTOM_STRATEGY_GUIDE.md`
2. 深入研究 `examples/` 中的示例
3. 实现复杂的策略和因子
4. 优化性能和稳定性

---

## 💬 常见问题

**Q: 我应该先写代码还是先写配置？**

A: 建议**先写代码**，确保可以导入，然后再写配置。

**Q: Handler 和 Strategy 的区别是什么？**

A:
- **Handler**: 计算因子/特征，继承 `Processor`
- **Strategy**: 管理训练流程，继承 `OnlineStrategy`

**Q: 可以同时使用多个自定义 Handler 吗？**

A: 可以！在配置中定义多个策略，每个使用不同的 Handler。

**Q: 如何调试我的 Handler？**

A: 在 `__call__` 方法中添加 print 语句，查看输入输出。

**Q: module_path 怎么写？**

A: Python 模块路径，如 `my_handlers.my_factors` 对应 `my_handlers/factors.py` 中的类。

---

## 🔗 相关链接

- [Qlib 官方文档](https://qlib.readthedocs.io/)
- [Handler API](https://qlib.readthedocs.io/en/latest/component/data.html#processor)
- [OnlineStrategy 源码](../qlib/workflow/online/strategy.py)

---

需要帮助？查看 `examples/` 中的完整示例！
