#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
回测工具快捷脚本

Usage:
    # 基础回测
    python scripts/run_backtest.py

    # 自定义参数
    python scripts/run_backtest.py --topk 50 --n-drop 5

    # 指定日期范围
    python scripts/run_backtest.py --start 2025-01-01 --end 2025-06-30

    # 使用配置文件
    python scripts/run_backtest.py --config config/backtest_config.yaml
"""

import argparse
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))


def main():
    parser = argparse.ArgumentParser(
        description="Qlib 策略回测工具",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # 策略参数
    parser.add_argument('--topk', type=int, default=30, help='持仓数量 (默认: 30)')
    parser.add_argument('--n-drop', type=int, default=3, help='调仓时卖出数量 (默认: 3)')
    parser.add_argument('--strategy', default='topk_dropout',
                       choices=['topk_dropout', 'topk', 'soft_topk'], help='策略类型')

    # 日期参数
    parser.add_argument('--start', help='回测开始日期 (YYYY-MM-DD)')
    parser.add_argument('--end', help='回测结束日期 (YYYY-MM-DD)')

    # 配置文件
    parser.add_argument('--config', help='回测配置文件 (YAML)')
    parser.add_argument('--manager-config', default='config/online_config.yaml',
                       help='Manager 配置文件')

    # 输出参数
    parser.add_argument('--output-dir', default='data/backtest', help='输出目录')
    parser.add_argument('--no-save', action='store_true', help='不保存结果')
    parser.add_argument('--no-plots', action='store_true', help='不生成图表')

    args = parser.parse_args()

    # 构建参数列表并直接运行主模块
    import subprocess

    cmd = [sys.executable, '-m', 'fqlib.run_backtest']

    if args.config:
        cmd.extend(['--config', args.config])
    else:
        cmd.extend(['--topk', str(args.topk)])
        cmd.extend(['--n-drop', str(args.n_drop)])
        cmd.extend(['--strategy-type', args.strategy])

        if args.start:
            cmd.extend(['--start', args.start])
        if args.end:
            cmd.extend(['--end', args.end])

        cmd.extend(['--exchange', 'SH'])
        cmd.extend(['--manager-config', args.manager_config])

    if args.no_save:
        cmd.append('--no-save')
    if args.no_plots:
        cmd.append('--no-plots')

    # 运行回测
    sys.exit(subprocess.run(cmd).returncode)


if __name__ == "__main__":
    main()
