# 量化训练工程 - 数据样本与目标集合配置详解

## 📋 目录
1. [训练样本设定机制](#训练样本设定机制)
2. [目标集合（股票池）配置](#目标集合股票池配置)
3. [全市场 vs 子集](#全市场-vs-子集)
4. [数据流完整解析](#数据流完整解析)
5. [实战配置示例](#实战配置示例)

---

## 训练样本设定机制

### 三层配置架构

```
┌─────────────────────────────────────────────────────────┐
│  Layer 1: YAML 配置文件                                 │
│  - 时间分段 (train/valid/test)                         │
│  - 滚动窗口配置                                         │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  Layer 2: DatasetH (数据集容器)                         │
│  - 管理数据加载                                         │
│  - 应用时间分段                                         │
│  - 数据预处理                                           │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  Layer 3: Alpha158 Handler (特征工程)                   │
│  - 选择目标股票池                                       │
│  - 计算 158 个金融特征                                  │
│  - 生成训练样本                                         │
└─────────────────────────────────────────────────────────┘
```

### 1. 时间分段配置

**当前配置** (`config/online_config.yaml`):
```yaml
segments:
  train: [2020-01-01, 2024-01-01]  # 训练期
  valid: [2024-01-01, 2025-01-01]  # 验证期
  test: [2025-01-01, 2026-01-01]   # 测试期
```

**关键要点**：

#### ✅ 时间序列分割（不是随机）
```python
# ❌ 错误理解：随机打乱数据
# 正确理解：按时间顺序分割

2020 ──────────► 2024 ─────► 2025 ─────► 2026
  train (4年)      valid (1年)   test (1年)
     ↓                ↓              ↓
  训练模型         调优参数      最终评估
```

**为什么这样设计？**
- 🎯 **模拟真实交易**：只能用过去的数据预测未来
- 🎯 **避免前瞻偏差**：测试数据必须在训练数据之后
- 🎯 **滚动训练**：定期用新数据重新训练模型

#### 滚动训练机制
```yaml
rolling_config:
  step: 90      # 每 90 天重新训练一次
  rtype: "ROLL_SD"  # 滑动窗口（保留最近 90 天数据）
```

**滚动训练示例**：
```
初始训练：2020-01-01 ─► 2023-12-31
           生成模型 v1

90 天后：2020-04-01 ─► 2024-03-31
         用新数据重训 → 模型 v2

再 90 天：2020-07-01 ─► 2024-06-30
          继续重训 → 模型 v3
```

### 2. 样本数量计算

**假设配置**：
- 股票池：500 只股票（CSI 500）
- 时间范围：4 年（2020-2024）
- 交易日：约 250 天/年 × 4 年 = 1000 个交易日

**样本数量**：
```
总样本数 = 股票数 × 交易日数
         = 500 × 1000
         = 500,000 个样本

每个样本包含：
- 158 个特征（Alpha158）
- 1 个目标变量（未来收益率）
```

**注意**：
- Qlib 会自动处理缺失数据
- 只使用有效交易的股票
- 每只股票的交易日可能不同

---

## 目标集合（股票池）配置

### 默认配置：CSI 500（不是全市场！）

**Qlib 的 Alpha158 默认**：
```python
# qlib/contrib/data/handler.py
class Alpha158(DataHandlerLP):
    def __init__(self, instruments="csi500", ...):
        """
        Args:
            instruments: 股票池配置
                - "csi300": 沪深 300（大盘股，300 只）
                - "csi500": 中证 500（中盘股，500 只）← 默认
                - "all": 全市场（5000+ 只）
                - "sse": 上证市场
                - "szse": 深证市场
                - 自定义列表：["sh.600000", "sz.000001"]
        """
```

### 检查你的股票池

```bash
# 运行检查脚本
python scripts/check_stock_pools.py
```

**预期输出**：
```
📊 CSI300
   描述: 沪深 300 指数成分股（大盘股）
   数量: 300 只股票
   示例: sh.600000, sh.600036, sh.600519, ...

📊 CSI500
   描述: 中证 500 指数成分股（中盘股）
   数量: 500 只股票
   示例: sh.600004, sh.600030, sz.000002, ...

📊 ALL
   描述: 所有可用股票
   数量: 5234 只股票
   示例: sh.600000, sh.600004, sz.000001, ...
```

### 如何修改股票池配置

#### 方式 1：修改 YAML 配置（推荐）

```yaml
# config/online_config.yaml
task_template:
  dataset:
    class: "DatasetH"
    module_path: "qlib.data.dataset"
    kwargs:
      handler:
        class: "Alpha158"
        module_path: "qlib.contrib.data.handler"
        instruments: "csi300"  # ← 修改这里
        # 或者自定义：
        # instruments: ["sh.600000", "sh.600036", "sz.000001"]
```

#### 方式 2：创建自定义 Handler

```python
# fqlib/custom_handler.py
from qlib.contrib.data.handler import Alpha158

class CustomAlpha158(Alpha158):
    """自定义股票池的 Handler"""
    def __init__(self, instruments="csi300", **kwargs):
        super().__init__(instruments=instruments, **kwargs)
```

然后在 YAML 中使用：
```yaml
handler:
  class: "CustomAlpha158"
  module_path: "fqlib.custom_handler"
  instruments: "csi300"
```

#### 方式 3：从文件读取股票列表

```bash
# 创建股票列表文件
cat > my_stocks.txt << EOF
sh.600000
sh.600036
sh.600519
sz.000001
sz.000002
EOF
```

```yaml
handler:
  class: "Alpha158"
  instruments: "my_stocks.txt"  # 从文件读取
```

---

## 全市场 vs 子集

### 当前配置：**子集（CSI 500）**

#### ❌ 不是全市场
```python
# ❌ 错误理解：训练所有 A 股
# ✅ 实际情况：只训练 CSI 500 成分股

全市场 A 股：         5000+ 只
实际训练（默认）：      500 只（CSI 500）
数据量比例：          10%
```

#### 为什么使用子集而不是全市场？

**优势**：
- ✅ **计算效率**：500 只 vs 5000 只，速度提升 10 倍
- ✅ **数据质量**：成分股流动性好，数据完整
- ✅ **代表性**：CSI 500 代表中盘股主流
- ✅ **稳定性**：成分股定期调整，剔除问题股票

**劣势**：
- ❌ **覆盖面**：可能错过小盘股机会
- ❌ **样本偏差**：成分股不代表整个市场

### 不同股票池的性能对比

| 股票池 | 股票数 | 训练时间 | 内存占用 | 适用场景 |
|--------|--------|----------|----------|----------|
| **CSI 300** | 300 | 1x | 低 | 大盘股策略 |
| **CSI 500** | 500 | 1.5x | 中 | **默认推荐** |
| **All** | 5000+ | 10x | 高 | 全市场扫描 |
| **自定义** | 可变 | 可变 | 可变 | 特定策略 |

### 如何选择股票池？

#### 1. **开发/测试阶段**（当前推荐）
```yaml
instruments: "csi300"  # 300 只，快速迭代
```

#### 2. **生产环境**（默认配置）
```yaml
instruments: "csi500"  # 500 只，平衡性能
```

#### 3. **全市场扫描**（需要更多资源）
```yaml
instruments: "all"  # 5000+ 只，计算密集
```

#### 4. **自定义股票池**（特定策略）
```yaml
# 例如：只关注科技股
instruments: ["sh.600036", "sz.000063", "sz.000333"]
```

---

## 数据流完整解析

### 完整的数据加载流程

```python
# 步骤 1：初始化 Qlib
# fqlib/util.py
init_qlib_from_config(config)
# → qlib.init(provider_uri="~/.qlib/qlib_data/cn_data", region="cn")
# → 加载市场数据、交易日历、股票列表

# 步骤 2：创建 Dataset
# fqlib/managed_manager.py
dataset = DatasetH(
    handler=Alpha158(instruments="csi500"),
    segments={
        "train": (2020-01-01, 2024-01-01),
        "valid": (2024-01-01, 2025-01-01),
        "test": (2025-01-01, 2026-01-01)
    }
)

# 步骤 3：Handler 加载数据
# Alpha158 内部逻辑
data = D.features(
    instruments=["sh.600000", "sh.600036", ...],  # CSI 500 成分股
    fields=[
        "$open", "$high", "$low", "$close", "$vwap", "$volume",
        "kbar/upper", "kbar/lower",  # Alpha158 特征
        # ... 158 个特征
    ],
    start_time="2020-01-01",
    end_time="2024-01-01"
)

# 步骤 4：特征工程
# Alpha158 处理
features = Alpha158.get_feature_config()
# → 生成 158 个金融特征
# → 处理缺失值
# → 标准化

# 步骤 5：生成训练样本
for stock in instruments:
    for date in trading_days:
        sample = {
            "features": [158 维向量],
            "label": 未来收益率,
            "weight": 样本权重
        }
```

### 数据结构示意

```
最终训练数据形状：
─────────────────────────────────────────────────────────────
Shape: (样本数, 158+1)
  - 样本数 = 股票数 × 交易日数 ≈ 500 × 1000 = 500,000
  - 特征数 = 158
  + 1 个标签（未来收益）

具体结构：
[
    [sh.600000, 2020-01-02]: [f1, f2, ..., f158, label],
    [sh.600000, 2020-01-03]: [f1, f2, ..., f158, label],
    ...
    [sz.000999, 2023-12-29]: [f1, f2, ..., f158, label],
]
─────────────────────────────────────────────────────────────
```

---

## 实战配置示例

### 示例 1：快速开发配置

```yaml
# config/online_config_dev.yaml
strategies:
  - name: "LGB_Dev"
    enabled: true
    task_template:
      model:
        class: "LGBModel"
        module_path: "qlib.contrib.model.gbdt"
        kwargs:
          num_leaves: 31  # 减少复杂度
          num_threads: 4

      dataset:
        class: "DatasetH"
        kwargs:
          handler:
            class: "Alpha158"
            instruments: "csi300"  # ← 只用 300 只股票

          segments:
            train: [2023-01-01, 2023-12-31]  # ← 只用 1 年数据
            valid: [2024-01-01, 2024-06-30]
            test: [2024-07-01, 2024-12-31]

      rolling_config:
        step: 180  # ← 减少滚动频率
```

**运行**：
```bash
python scripts/first_run.py --config config/online_config_dev.yaml
```

**预期时间**：~5-10 分钟

### 示例 2：生产配置

```yaml
# config/online_config_prod.yaml
strategies:
  - name: "LGB_Prod"
    enabled: true
    task_template:
      dataset:
        kwargs:
          handler:
            instruments: "csi500"  # ← 500 只股票

          segments:
            train: [2020-01-01, 2024-01-01]  # ← 4 年数据
            valid: [2024-01-01, 2025-01-01]
            test: [2025-01-01, 2026-01-01]

      rolling_config:
        step: 90  # ← 每 90 天重训
```

**预期时间**：~30-60 分钟

### 示例 3：全市场配置

```yaml
# config/online_config_fullmarket.yaml
strategies:
  - name: "LGB_FullMarket"
    enabled: true
    task_template:
      dataset:
        kwargs:
          handler:
            instruments: "all"  # ← 全市场 5000+ 只股票

          segments:
            train: [2020-01-01, 2024-01-01]
            valid: [2024-01-01, 2025-01-01]
            test: [2025-01-01, 2026-01-01]

      rolling_config:
        step: 90
```

**预期时间**：~2-5 小时
**内存需求**：16GB+

---

## 总结与建议

### 关键要点

1. **✅ 当前配置**
   - 股票池：CSI 500（500 只中盘股）
   - 时间范围：2020-2026（6 年）
   - 样本数：约 500,000 个
   - **不是全市场训练**

2. **🎯 训练样本设定**
   - 三层架构：配置 → Dataset → Handler
   - 时间序列分割（不是随机）
   - 滚动训练机制（90 天）

3. **📊 股票池配置**
   - 默认：CSI 500
   - 可选：CSI 300, All, SSE, SZSE
   - 可自定义

### 实战建议

#### 开发阶段
```yaml
instruments: "csi300"      # 300 只，快速验证
train: 1 年数据             # 减少训练时间
```

#### 测试阶段
```yaml
instruments: "csi500"      # 500 只，默认配置
train: 4 年数据             # 充分训练
```

#### 生产阶段
```yaml
instruments: "csi500"      # 或自定义股票池
train: 4+ 年数据            # 使用更多历史数据
rolling:
  step: 30                 # 更频繁更新
```

### 检查工具

```bash
# 1. 检查股票池
python scripts/check_stock_pools.py

# 2. 检查数据范围
python scripts/simple_data_check.py

# 3. 运行快速测试
python scripts/quick_test.py --reset
```

---

## 常见问题

### Q1: 如何训练全市场？
```yaml
# 修改配置
handler:
  instruments: "all"  # 全市场
```

### Q2: 如何只训练特定股票？
```yaml
# 方式 1：列表
handler:
  instruments: ["sh.600000", "sz.000001"]

# 方式 2：文件
handler:
  instruments: "my_stocks.txt"
```

### Q3: 样本数如何计算？
```python
样本数 = 股票数 × 交易日数
       = 500 × 1000
       = 500,000
```

### Q4: 如何减少训练时间？
```yaml
# 1. 减少股票数
instruments: "csi300"  # 300 vs 500

# 2. 减少时间范围
train: [2023-01-01, 2023-12-31]  # 1 年 vs 4 年

# 3. 减少滚动频率
step: 180  # 180 天 vs 90 天
```
