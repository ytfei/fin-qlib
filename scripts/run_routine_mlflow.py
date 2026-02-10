#!/usr/bin/env python
# Copyright (c) 2024
# Licensed under the MIT License.

"""
Online Manager Routine Script with MLflow Integration

带有 MLflow 集成的日常更新脚本。

Usage:
    python run_routine_mlflow.py --config config/online_config_mlflow.yaml
    python run_routine_mlflow.py --config config/online_config_mlflow.yaml --cur-time 2024-01-15
"""

import argparse
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fqlib.managed_manager import ManagedOnlineManager
import qlib
import yaml


def init_qlib_from_config(config: dict):
    """Initialize Qlib based on configuration."""
    qlib_config = config.get('qlib_config', {})

    provider_uri = qlib_config.get('provider_uri', '~/.qlib/qlib_data/cn_data')
    region = qlib_config.get('region', 'cn')

    # Build initialization kwargs
    init_kwargs = {
        'provider_uri': provider_uri,
        'region': region,
    }

    # MLflow configuration
    mlflow_uri = qlib_config.get('mlflow_tracking_uri')
    if mlflow_uri:
        init_kwargs['flask_server'] = True
        init_kwargs['mlflow_tracking_uri'] = mlflow_uri
        print(f"MLflow tracking URI: {mlflow_uri}")

    # MongoDB configuration
    mongo_config = qlib_config.get('mongo', {})
    if mongo_config.get('enabled', False):
        init_kwargs['mongo'] = {
            'task_url': mongo_config.get('task_url'),
            'task_db_name': mongo_config.get('task_db_name'),
        }
        print(f"MongoDB enabled: {mongo_config['task_url']}")

    # Initialize Qlib
    try:
        qlib.init(**init_kwargs)
        print("Qlib initialized successfully")
    except Exception as e:
        print(f"Failed to initialize Qlib: {e}")
        raise


def setup_mlflow_integration(manager, mlflow_config: dict):
    """
    设置 MLflow 集成

    Args:
        manager: ManagedOnlineManager 实例
        mlflow_config: MLflow 配置字典
    """
    if not mlflow_config.get('enabled', False):
        print("MLflow integration disabled")
        return

    from fqlib.mlflow_integration import (
        MLflowLogger,
        MLflowEnabledStrategy,
        QlibBacktestAnalyzer
    )

    print("Setting up MLflow integration...")

    # 创建 MLflow Logger
    mlflow_logger = MLflowLogger(
        experiment_name=mlflow_config.get('experiment_name', 'qlib_online'),
        tracking_uri=mlflow_config.get('tracking_uri'),
        auto_start=True  # 自动开始 run
    )

    # 包装所有策略
    wrapped_strategies = []
    for strategy in manager.manager.strategies:
        wrapped_strategy = MLflowEnabledStrategy(strategy, mlflow_logger)
        wrapped_strategies.append(wrapped_strategy)

    # 替换原始策略
    manager.manager.strategies = wrapped_strategies

    # 保存回测分析器供后续使用
    manager.mlflow_backtest_analyzer = QlibBacktestAnalyzer(mlflow_logger)
    manager.mlflow_logger = mlflow_logger
    manager.mlflow_config = mlflow_config

    print(f"MLflow integration enabled. Run ID: {mlflow_logger.run_id}")


def run_auto_backtest(manager):
    """运行自动回测"""
    if not hasattr(manager, 'mlflow_config'):
        return

    backtest_config = manager.mlflow_config.get('auto_backtest', {})
    if not backtest_config.get('enabled', False):
        print("Auto backtest disabled")
        return

    print("\n" + "=" * 80)
    print("Running Auto Backtest")
    print("=" * 80)

    from qlib.data import D
    import pandas as pd

    # 获取回测参数
    top_n = backtest_config.get('top_n', 50)
    lookback_days = backtest_config.get('lookback_days', 30)

    # 计算回测日期范围
    cur_time = manager.manager.cur_time
    end_date = cur_time
    start_date = cur_time - pd.Timedelta(days=lookback_days)

    print(f"Backtest period: {start_date} to {end_date}")
    print(f"Top N: {top_n}")

    # 获取基准数据
    benchmark_config = backtest_config.get('benchmark', {})
    benchmark_returns = None

    if benchmark_config.get('enabled', False):
        benchmark_inst = benchmark_config.get('instrument', 'SH000300')
        print(f"Loading benchmark: {benchmark_inst}")

        try:
            # 获取基准指数数据
            benchmark_df = D.features(
                instruments=[benchmark_inst],
                fields=["$return"],
                start_time=start_date,
                end_time=end_date
            )

            if benchmark_df is not None and len(benchmark_df) > 0:
                benchmark_returns = benchmark_df.iloc[:, 0] if isinstance(benchmark_df, pd.DataFrame) else benchmark_df
                print(f"Loaded {len(benchmark_returns)} benchmark returns")
            else:
                print("Warning: No benchmark data available")

        except Exception as e:
            print(f"Warning: Failed to load benchmark: {e}")

    # 对每个策略运行回测
    for strategy in manager.manager.strategies:
        print(f"\nBacktesting strategy: {strategy.name_id}")

        try:
            # 使用包装策略的回测方法
            if hasattr(strategy, 'run_backtest_and_log'):
                strategy.run_backtest_and_log(
                    start_date=str(start_date.date()),
                    end_date=str(end_date.date()),
                    benchmark_data=benchmark_returns
                )
            else:
                print(f"Warning: Strategy {strategy.name_id} does not support backtest")

        except Exception as e:
            print(f"Error backtesting {strategy.name_id}: {e}")
            import traceback
            traceback.print_exc()


def main():
    parser = argparse.ArgumentParser(
        description="Run Online Manager routine with MLflow integration",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--config',
        type=str,
        default='config/online_config_mlflow.yaml',
        help='Path to configuration file (default: config/online_config_mlflow.yaml)'
    )

    parser.add_argument(
        '--cur-time',
        type=str,
        default=None,
        help='Current time for routine (YYYY-MM-DD format). If not specified, uses latest date.'
    )

    parser.add_argument(
        '--sync',
        action='store_true',
        help='Sync strategies with configuration file before running routine'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Dry run: simulate routine without actual training'
    )

    parser.add_argument(
        '--status',
        action='store_true',
        help='Show manager status and exit'
    )

    parser.add_argument(
        '--log-dir',
        type=str,
        default='logs',
        help='Log directory (default: logs)'
    )

    parser.add_argument(
        '--skip-backtest',
        action='store_true',
        help='Skip auto backtest even if enabled in config'
    )

    args = parser.parse_args()

    # Check if config file exists
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Configuration file not found: {config_path}")
        print(f"\nPlease create a configuration file or use --config to specify one.")
        sys.exit(1)

    # Load configuration
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Initialize Qlib
    print("=" * 80)
    print("Initializing Qlib")
    print("=" * 80)
    init_qlib_from_config(config)

    # Create manager
    print("\n" + "=" * 80)
    print("Creating/Loading Manager")
    print("=" * 80)

    try:
        manager = ManagedOnlineManager(
            config_path=str(config_path),
            log_dir=args.log_dir
        )
    except Exception as e:
        print(f"Failed to create manager: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Setup MLflow integration
    mlflow_config = config['online_manager'].get('mlflow_integration', {})
    setup_mlflow_integration(manager, mlflow_config)

    # Show status if requested
    if args.status:
        print("\n" + "=" * 80)
        print("Manager Status")
        print("=" * 80)
        manager.print_status()
        sys.exit(0)

    # Sync strategies if requested
    if args.sync:
        print("\n" + "=" * 80)
        print("Syncing Strategies")
        print("=" * 80)
        try:
            manager.sync_strategies()
        except Exception as e:
            print(f"Strategy sync failed: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

    # Show current status
    manager.print_status()

    # Dry run
    if args.dry_run:
        print("\n" + "=" * 80)
        print("DRY RUN - Skipping actual routine execution")
        print("=" * 80)
        print("Would execute routine with:")
        print(f"  cur_time: {args.cur_time or 'latest'}")
        print(f"  strategies: {len(manager.manager.strategies)}")
        print(f"  mlflow enabled: {mlflow_config.get('enabled', False)}")
        sys.exit(0)

    # Run routine
    print("\n" + "=" * 80)
    print("Running Routine with MLflow")
    print("=" * 80)

    try:
        manager.run_routine(cur_time=args.cur_time)

        print("\n" + "=" * 80)
        print("Routine Completed Successfully")
        print("=" * 80)
        manager.print_status()

        # Show signal summary
        signals = manager.get_signals()
        if signals is not None and len(signals) > 0:
            print("\n" + "=" * 80)
            print("Signal Summary")
            print("=" * 80)

            if isinstance(signals, pd.DataFrame):
                latest_date = signals.index.get_level_values('datetime').max()
                latest_signals = signals.loc[latest_date]
            else:
                latest_date = signals.index.get_level_values('datetime').max()
                latest_signals = signals[signals.index.get_level_values('datetime') == latest_date]

            print(f"Latest signals date: {latest_date}")
            print(f"Number of stocks: {len(latest_signals)}")

            # Show top 10
            if isinstance(latest_signals, pd.DataFrame):
                top_10 = latest_signals.iloc[:, 0].nlargest(10)
            else:
                top_10 = latest_signals.nlargest(10)

            print("\nTop 10 stocks:")
            for stock, score in top_10.items():
                print(f"  {stock}: {score:.4f}")

        # Run auto backtest
        if not args.skip_backtest:
            run_auto_backtest(manager)

        # End MLflow run
        if hasattr(manager, 'mlflow_logger'):
            manager.mlflow_logger.end_run()
            print(f"\nMLflow run ended: {manager.mlflow_logger.run_id}")
            print("View results at: http://localhost:5000")

    except Exception as e:
        print(f"\nRoutine failed: {e}")
        import traceback
        traceback.print_exc()

        # End MLflow run with FAILED status
        if hasattr(manager, 'mlflow_logger'):
            manager.mlflow_logger.end_run(status="FAILED")

        sys.exit(1)

    print("\n" + "=" * 80)
    print("Done!")
    print("=" * 80)


if __name__ == "__main__":
    import pandas as pd
    main()
