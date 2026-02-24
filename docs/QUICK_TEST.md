# Quick Test Guide - Minimal Configuration

本指南帮助你使用最小化配置快速测试系统是否正常工作。

## 📋 前置检查

### 1. 检查数据范围

首先确认你有可用的数据：

```bash
python scripts/simple_data_check.py
```

这会显示：
- 可用的股票市场
- 实际数据的日期范围
- 推荐的配置日期

**示例输出：**
```
✓ Market 'all': 5000+ instruments
Date range: 2020-01-02 to 2024-12-31
Total records: 1200
```

### 2. 根据数据更新配置

如果你的数据范围与配置不匹配，修改 `config/online_config_minimal.yaml`：

```yaml
segments:
  train: [2022-01-01, 2022-12-31]  # 改为你的数据范围
  valid: [2023-01-01, 2023-06-30]
  test: [2023-07-01, 2023-12-31]
```

## 🚀 运行快速测试

### 方式 1：使用快速测试脚本（推荐）

```bash
# 首次测试（会清理旧的检查点）
python scripts/quick_test.py --reset

# 后续测试（保留检查点）
python scripts/quick_test.py
```

### 方式 2：手动执行

```bash
# 1. 运行首次训练
python scripts/first_run.py --config config/online_config_minimal.yaml

# 2. 运行日常流程
python scripts/run_routine.py --config config/online_config_minimal.yaml
```

## ✅ 预期结果

### 成功输出示例

```
================================================================================
Quick Test - Minimal Configuration
================================================================================

1️⃣  Initializing Qlib...
✓ Qlib initialized successfully

2️⃣  Creating Manager...
✓ Manager created successfully

3️⃣  Running First Training...
[INFO] Strategy LGB_Minimal_Test begins first training...
✓ First training completed successfully

4️⃣  Checking Status...
✓ Current time: 2023-12-31
✓ Strategies: LGB_Minimal_Test
✓ Signals: YES
  - Signal count: 500
  - Date range: 2023-07-01 to 2023-12-31

5️⃣  Testing Routine...
✓ Routine completed successfully

================================================================================
✅ Quick Test PASSED!
================================================================================
```

### 生成的文件

测试成功后，会生成以下文件：

```
data/
├── checkpoints/
│   └── online_manager_minimal.pkl  # 模型检查点
├── logs/
│   └── online_manager_*.log        # 日志文件
├── signals/
│   ├── signals_20231231.csv        # 交易信号
│   └── signals_latest.csv          # 最新信号
└── mlflow.db                       # MLflow 数据库
```

## 🔧 故障排除

### 问题 1: IndexError / index out of bounds

**错误：**
```
IndexError: index 4943 is out of bounds for axis 0 with size 4943
```

**原因：** 配置的日期超出实际数据范围

**解决：**
```bash
# 1. 检查实际数据范围
python scripts/simple_data_check.py

# 2. 更新 config/online_config_minimal.yaml 中的 segments
# 确保 test 的结束日期 <= 实际数据的最新日期
```

### 问题 2: No instruments found

**错误：**
```
Total instruments: 0
```

**原因：** Qlib 数据未正确安装或路径错误

**解决：**
```bash
# 1. 检查数据是否存在
ls -la ~/.qlib/qlib_data/cn_data/

# 2. 如果数据不存在，重新下载
python -m qlib.download_data --target_dir ~/.qlib/qlib_data/cn_data --region cn

# 3. 或使用已有数据的正确路径
# 修改 config 中的 provider_uri
```

### 问题 3: Memory Error

**错误：**
```
MemoryError: Unable to allocate array
```

**解决：**
```yaml
# 在配置中减少线程数
model:
  kwargs:
    num_threads: 2  # 减少到 2

# 或使用更少的数据
segments:
  train: [2023-01-01, 2023-06-30]  # 减少到 6 个月
```

### 问题 4: Module not found

**错误：**
```
ModuleNotFoundError: No module named 'qlib'
```

**解决：**
```bash
# 安装 pyqlib
pip install pyqlib-2026.2.8.*.whl

# 或从源码安装
cd ../qlib
pip install -e .
```

## 📊 性能参考

| 配置 | 数据量 | 预计时间 |
|------|--------|----------|
| Minimal | 1 年训练 + 各 6 个月验证/测试 | ~5-10 分钟 |
| Simple | 2 年训练 + 各 6 个月验证/测试 | ~10-20 分钟 |
| Full | 4 年训练 + 各 1 年验证/测试 | ~30-60 分钟 |

## 🎯 测试检查清单

运行测试前，确保：

- [ ] Qlib 已正确安装
- [ ] 数据已下载并可用
- [ ] 配置文件中的日期在数据范围内
- [ ] 有足够的磁盘空间（至少 1GB）
- [ ] 有足够的内存（至少 4GB）

测试成功后，你应该看到：

- [ ] ✓ First training 完成无错误
- [ ] ✓ 生成了 checkpoint 文件
- [ ] ✓ 生成了 signals 文件
- [ ] ✓ 日志文件中有训练记录
- [ ] ✓ 可以运行 routine 无错误

## 📝 下一步

测试通过后，可以：

1. **使用完整配置**
   ```bash
   python scripts/first_run.py --config config/online_config.yaml
   ```

2. **添加更多策略**
   - 编辑 `config/online_config.yaml`
   - 在 `strategies` 部分添加新策略

3. **设置定时任务**
   ```bash
   # 编辑 crontab
   crontab -e

   # 添加每日任务（工作日 16:30）
   30 16 * * 1-5 cd /path/to/fin-qlib && python scripts/run_routine.py --config config/online_config_minimal.yaml >> data/logs/routine.log 2>&1
   ```

## 💡 提示

- **首次使用**：先用 `--reset` 参数清理旧数据
- **调试时**：查看 `data/logs/` 中的详细日志
- **性能优化**：调整 `rolling_config.step` 来减少任务数量
- **数据更新**：定期运行 `run_routine.py` 更新模型

## 🆘 需要帮助？

如果遇到问题：

1. 查看日志：`tail -f data/logs/online_manager_*.log`
2. 检查数据：`python scripts/simple_data_check.py`
3. 运行诊断：`python scripts/check_data_range.py`
