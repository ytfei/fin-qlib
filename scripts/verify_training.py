#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
验证首次训练结果

Usage:
    python scripts/verify_training.py
"""

import sys
import pickle
import yaml
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import qlib
from fqlib.util import init_qlib_from_config


def verify_training():
    """验证训练结果"""

    print("=" * 80)
    print("验证首次训练结果")
    print("=" * 80)

    # 初始化 Qlib
    print("\n初始化 Qlib...")
    config_path = Path("config/online_config.yaml")
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        init_qlib_from_config(config)
        print("✓ Qlib 初始化成功")
    else:
        # 使用默认配置
        qlib.init(provider_uri="~/.qlib/qlib_data/cn_data", region="cn")
        print("✓ Qlib 初始化成功（使用默认配置）")

    # 1. 检查 checkpoint
    checkpoint_path = Path("data/checkpoints/online_manager.pkl")
    if not checkpoint_path.exists():
        print(f"\n❌ Checkpoint 不存在: {checkpoint_path}")
        print("\n请先运行首次训练：")
        print("  python scripts/first_run.py --config config/online_config.yaml")
        return

    print(f"\n✓ Checkpoint 存在")
    print(f"  文件大小: {checkpoint_path.stat().st_size / 1024:.2f} KB")

    # 2. 加载 manager
    print("\n" + "=" * 80)
    print("加载 Manager...")
    print("=" * 80)

    try:
        with open(checkpoint_path, 'rb') as f:
            manager = pickle.load(f)

        print(f"✓ Manager 加载成功")
        print(f"  当前时间: {manager.cur_time}")
        print(f"  策略数量: {len(manager.strategies)}")

        for strategy in manager.strategies:
            print(f"\n  策略: {strategy.name_id}")

            # 检查在线模型
            tool = strategy.tool
            online_models = tool.online_models()

            print(f"    在线模型数量: {len(online_models)}")

            if online_models:
                print(f"\n    ✓ 训练成功！有 {len(online_models)} 个在线模型")
                print(f"\n    模型详情:")
                for i, model_rec in enumerate(online_models):
                    rec_id = model_rec.info['id']
                    print(f"      模型 {i+1}: {rec_id[:12]}...")

                    # 检查预测数据
                    try:
                        pred = model_rec.load_object("pred.pkl")
                        if pred is not None:
                            if hasattr(pred, 'index'):
                                dates = pred.index.get_level_values('datetime')
                                print(f"        预测范围: {dates.min()} to {dates.max()}")
                                print(f"        预测数量: {len(pred)} 个")
                            else:
                                print(f"        预测数据: {type(pred)}")
                        else:
                            print(f"        ⚠️  预测数据: None")
                    except Exception as e:
                        print(f"        ⚠️  无法加载预测: {e}")

                # 验证是否可以运行 routine
                print(f"\n    ✓ 可以运行 run_routine.py 了！")
                print(f"\n    使用命令:")
                print(f"      python scripts/run_routine.py --cur-time 2026-02-23")

            else:
                print(f"    ❌ 没有在线模型！训练可能失败")
                print(f"\n    建议：重新运行首次训练")
                print(f"      rm data/checkpoints/online_manager.pkl")
                print(f"      python scripts/first_run.py --config config/online_config.yaml")

        # 3. 检查信号
        print("\n" + "=" * 80)
        print("检查交易信号")
        print("=" * 80)

        signals = manager.get_signals()
        if signals is not None:
            print(f"✓ 有信号数据: {len(signals)} 个")
            if hasattr(signals, 'index'):
                dates = signals.index.get_level_values('datetime')
                print(f"  日期范围: {dates.min()} to {dates.max()}")
        else:
            print(f"⚠️  暂无信号数据（正常，需要运行 routine 后才会有）")

    except Exception as e:
        print(f"❌ 加载 Manager 失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    verify_training()
