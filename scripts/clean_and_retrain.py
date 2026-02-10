#!/usr/bin/env python
# Copyright (c) 2024
# Licensed under the MIT License.

"""
Clean up and retrain models that are missing pred.pkl
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import qlib
from qlib.workflow import R


def clean_models_missing_pred():
    """Delete models that are missing pred.pkl file."""

    # Initialize Qlib
    qlib.init(provider_uri='~/.qlib/qlib_data/cn_data', region='cn')

    print("=" * 80)
    print("清理缺少 pred.pkl 的模型")
    print("=" * 80)

    exp = R.get_exp(experiment_name='LGB_Alpha158')
    recorders_dict = exp.list_recorders()

    to_delete = []
    to_keep = []

    for rid, rec in recorders_dict.items():
        artifacts = rec.list_artifacts()
        has_pred = 'pred.pkl' in artifacts

        if has_pred:
            to_keep.append(rid)
            print(f'✓ 模型 {rid[:8]}... - 有 pred.pkl，保留')
        else:
            to_delete.append(rid)
            print(f'✗ 模型 {rid[:8]}... - 缺少 pred.pkl，将删除')

    print(f'\n统计:')
    print(f'  保留: {len(to_keep)} 个模型')
    print(f'  删除: {len(to_delete)} 个模型')

    if to_delete:
        confirm = input(f'\n确认删除 {len(to_delete)} 个有问题的模型？(yes/no): ')
        if confirm.lower() == 'yes':
            for rid in to_delete:
                exp.delete_recorder(rid)
                print(f'  已删除: {rid[:8]}...')
            print('\n清理完成！')
            print('下一步：运行 python scripts/first_run.py 重新训练')
        else:
            print('取消删除')
    else:
        print('没有需要清理的模型')

    print("=" * 80)


if __name__ == "__main__":
    clean_models_missing_pred()
