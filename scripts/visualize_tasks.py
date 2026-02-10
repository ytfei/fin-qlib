#!/usr/bin/env python
# Copyright (c) 2024
# Licensed under the MIT License.

"""
Visualize routine task generation process.
"""

from datetime import datetime, timedelta
import json


def analyze_task_generation():
    """Analyze and visualize task generation."""

    # From the logs
    last_test_start = datetime(2022, 12, 26)
    current_time = datetime(2026, 1, 21)
    rolling_step_days = 30  # Trading days (approximately)
    interval_days = 744  # From log

    print("=" * 80)
    print("ROUTINE 任务生成可视化分析")
    print("=" * 80)
    print()

    print("📊 基本信息:")
    print(f"  • 当前时间: {current_time.strftime('%Y-%m-%d')}")
    print(f"  • 上次训练: {last_test_start.strftime('%Y-%m-%d')}")
    print(f"  • 时间间隔: {interval_days} 个交易日")
    print(f"  • 滚动步长: {rolling_step_days} 天")
    print()

    print("📈 任务生成原理:")
    print("  RollingStrategy 会每隔 N 天（滚动步长）重新训练一个新模型")
    print("  这样可以确保模型始终使用最新的市场数据")
    print()

    # Calculate task count
    task_count = interval_days // rolling_step_days
    print(f"🔢 任务数量计算:")
    print(f"  任务数 = 间隔天数 / 滚动步长")
    print(f"  任务数 = {interval_days} / {rolling_step_days}")
    print(f"  任务数 ≈ {task_count}")
    print()

    print("📅 生成的任务时间线:")
    print()

    # Show first few and last few tasks
    print("  前 5 个任务:")
    for i in range(min(5, task_count)):
        task_start = last_test_start + timedelta(days=i * rolling_step_days)
        task_end = task_start + timedelta(days=rolling_step_days)
        print(f"    任务 {i+1:2d}. test [{task_start.strftime('%Y-%m-%d')}, {task_end.strftime('%Y-%m-%d')}]")

    if task_count > 10:
        print(f"    ... 省略 {task_count - 10} 个任务 ...")

        print("  后 5 个任务:")
        for i in range(max(5, task_count - 5), task_count):
            task_start = last_test_start + timedelta(days=i * rolling_step_days)
            task_end = task_start + timedelta(days=rolling_step_days)
            if task_end > current_time:
                task_end = current_time
            print(f"    任务 {i+1:2d}. test [{task_start.strftime('%Y-%m-%d')}, {task_end.strftime('%Y-%m-%d')}]")

    print()

    print("🎯 每个任务包含:")
    print("  ┌─────────────────────────────────────┐")
    print("  │  Model: LightGBM                     │")
    print("  │  Dataset:                            │")
    print("  │    - Train: 2年滚动窗口              │")
    print("  │    - Valid: 6个月                    │")
    print("  │    - Test:  30天 (当前任务的目标)   │")
    print("  │  Output:                              │")
    print("  │    - 训练好的模型                    │")
    print("  │    - Test 期预测                     │")
    print("  │    - 保存到 MLflow Recorder          │")
    print("  └─────────────────────────────────────┘")
    print()

    print("⚙️  执行流程:")
    print("""
    1️⃣  prepare_tasks()
       └─> 检测时间间隔
       └─> 生成 24 个任务配置

    2️⃣  trainer.train(24个任务)
       └─> 任务1: 加载数据 → 训练 → 保存 (54秒)
       └─> 任务2: 加载数据 → 训练 → 保存 (54秒)
       └─> 任务3: 加载数据 → 训练 → 保存 (54秒)
       │   ...
       └─> 任务24: 加载数据 → 训练 → 保存 (54秒)

    3️⃣  prepare_online_models()
       └─> 将 24 个新模型标记为 "online"

    4️⃣  prepare_signals()
       └─> 收集所有 online 模型的预测
       └─> 集成（平均/加权等）
       └─> 生成最终交易信号
    """)

    print("⏱️  时间估算:")
    avg_time_per_task = 54  # seconds from log
    total_time = task_count * avg_time_per_task
    print(f"  • 每个任务: ~{avg_time_per_task} 秒")
    print(f"  • 24 个任务: ~{total_time} 秒 ≈ {total_time/60:.1f} 分钟")
    print()

    print("💡 为什么需要这么多任务？")
    print("""
    答案：为了适应市场变化

    • 2022年的市场环境 ≠ 2025年的市场环境
    • 使用旧模型可能无法捕捉新的市场规律
    • 滚动训练确保模型始终"与时俱进"

    类比：
    就像天气预报需要每天更新，
    量化模型也需要定期更新以适应市场变化。
    """)

    print("🔧 如何减少任务数量？")
    print("""
    方法1: 增加滚动步长
      rolling_config:
        step: 90  # 30天 → 90天，任务数减少67%

    方法2: 使用固定模型（不推荐用于生产）
      禁用滚动，只训练一次

    方法3: 并行训练（加快速度）
      使用 TrainerRM 替代 TrainerR
    """)

    print("=" * 80)
    print("总结")
    print("=" * 80)
    print(f"""
  你执行 run_routine.py 时产生了 {task_count} 个任务，这是正常的！

  原因：
  • 从上次训练到现在有 {interval_days} 天
  • 每隔 {rolling_step_days} 天需要重新训练模型
  • 系统自动补齐了所有中间的任务

  这些任务是：
  • 训练任务 - 每个训练一个新的 LightGBM 模型
  • 使用不同时间段的数据
  • 最终会生成 {task_count} 个在线模型
  • 用于生成最新的交易信号

  执行时间：约 {total_time/60:.0f} 分钟
    """)
    print("=" * 80)


def show_rolling_diagram():
    """Show rolling strategy diagram."""
    print()
    print("=" * 80)
    print("滚动策略示意图")
    print("=" * 80)
    print("""
    时间轴 (2022 → 2026):

    2022-12                    2024-06                    2026-01
      |───────────────────────────|───────────────────────────|
      |
      上次训练 (模型 A)
      test: [2022-12, 2023-01]

      |──30d──> ──30d──> ──30d──> ──30d──> ... ──30d──> ──30d──>
        任务1     任务2     任务3     任务4            任务23    任务24
        模型B     模型C     模型D     模型E            模型Y     模型Z

    每个任务：
    ┌────────────────────────────────────────┐
    │ Train: 滚动窗口 (如 2020-01 ~ 2022-XX) │
    │ Valid: 滚动窗口 (如 2022-XX ~ 2022-XX) │
    │ Test:  30天     (如 2022-XX ~ 2023-XX) │
    │                                        │
    │ → 训练 LightGBM 模型                   │
    │ → 在 Test 期生成预测                   │
    │ → 保存为 Online Recorder               │
    └────────────────────────────────────────┘

    最终结果：
    • 24 个模型同时处于 "online" 状态
    • 每个模型负责不同时间段的预测
    • prepare_signals() 会收集所有模型的预测
    • 通过集成方法生成最终信号
    """)
    print("=" * 80)


if __name__ == "__main__":
    analyze_task_generation()
    show_rolling_diagram()
