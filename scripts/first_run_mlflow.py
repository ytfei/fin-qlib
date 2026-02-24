#!/usr/bin/env python
# Copyright (c) 2024
# Licensed under the MIT License.

"""
First Run Script with MLflow Integration

初始化和首次训练脚本，支持 MLflow 集成。

Usage:
    python first_run_mlflow.py --config config/online_config_mlflow.yaml
    python first_run_mlflow.py --config config/online_config_mlflow.yaml --reset
"""

import argparse
import sys
import os
import shutil
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
import qlib
from fqlib.managed_manager import ManagedOnlineManager
from fqlib.util import init_qlib_from_config


def reset_manager(manager_path: Path):
    """
    Remove existing manager checkpoint and experiment data.

    WARNING: This will delete all trained models and predictions!
    """
    print("=" * 80)
    print("RESET MODE - This will delete all existing data!")
    print("=" * 80)

    # Remove checkpoint
    if manager_path.exists():
        print(f"Removing checkpoint: {manager_path}")
        os.remove(manager_path)

    # Optionally remove MLflow experiments
    # NOTE: This would require additional implementation
    # mlflow.delete_experiment(experiment_id)

    print("Reset complete!")


def main():
    parser = argparse.ArgumentParser(
        description="Initialize Online Manager with MLflow and run first training",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--config',
        type=str,
        default='config/online_config_mlflow.yaml',
        help='Path to configuration file (default: config/online_config_mlflow.yaml)'
    )

    parser.add_argument(
        '--reset',
        action='store_true',
        help='Reset existing manager (delete checkpoint and models) before running'
    )

    parser.add_argument(
        '--log-dir',
        type=str,
        default='data/logs',
        help='Log directory (default: logs)'
    )

    args = parser.parse_args()

    # Load configuration
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Configuration file not found: {config_path}")
        print("\nPlease create a configuration file first:")
        print("  cp config/online_config_mlflow.yaml config/my_config.yaml")
        print("  # Then edit config/my_config.yaml with your settings")
        sys.exit(1)

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Check if reset requested
    manager_path_str = config['online_manager'].get('manager_path', 'data/checkpoints/online_manager.pkl')
    manager_path = Path(manager_path_str)

    if args.reset:
        response = input("This will delete all existing models and predictions. Continue? (yes/no): ")
        if response.lower() == 'yes':
            reset_manager(manager_path)
        else:
            print("Reset cancelled")
            sys.exit(0)

    # Initialize Qlib
    print("=" * 80)
    print("Initializing Qlib")
    print("=" * 80)

    init_qlib_from_config(config)

    # Setup MLflow integration before creating manager
    print("\n" + "=" * 80)
    print("Setting up MLflow Integration")
    print("=" * 80)

    mlflow_config = config['online_manager'].get('mlflow_integration', {})
    if mlflow_config.get('enabled', False):
        print(f"MLflow enabled: {mlflow_config.get('experiment_name', 'qlib_online')}")
        print(f"Tracking URI: {mlflow_config.get('tracking_uri', 'local filesystem')}")
        print(f"Auto backtest: {mlflow_config.get('auto_backtest', {}).get('enabled', False)}")
    else:
        print("MLflow integration disabled")

    # Create manager and run first training
    print("\n" + "=" * 80)
    print("Creating Manager and Running First Training")
    print("=" * 80)

    try:
        manager = ManagedOnlineManager(
            config_path=str(config_path),
            log_dir=args.log_dir
        )

        # Setup MLflow integration for the manager
        if mlflow_config.get('enabled', False):
            from fqlib.mlflow_integration import MLflowLogger, MLflowEnabledStrategy

            mlflow_logger = MLflowLogger(
                experiment_name=mlflow_config.get('experiment_name', 'qlib_online'),
                tracking_uri=mlflow_config.get('tracking_uri'),
                auto_start=True
            )

            print(f"MLflow run started: {mlflow_logger.run_id}")

            # Wrap strategies
            wrapped_strategies = []
            for strategy in manager.manager.strategies:
                wrapped = MLflowEnabledStrategy(strategy, mlflow_logger)
                wrapped_strategies.append(wrapped)

            manager.manager.strategies = wrapped_strategies

            # Save for later use
            manager.mlflow_logger = mlflow_logger
            manager.mlflow_config = mlflow_config

        print("\n" + "=" * 80)
        print("First Training Completed Successfully!")
        print("=" * 80)

        # Show status
        manager.print_status()

        if hasattr(manager, 'mlflow_logger'):
            print(f"\nMLflow Run ID: {manager.mlflow_logger.run_id}")
            print("View experiments at: http://localhost:5000")

            # End the run
            manager.mlflow_logger.end_run()
            print("MLflow run ended")

        print("\n" + "=" * 80)
        print("Next Steps:")
        print("=" * 80)
        print("1. Review the trained models and predictions in MLflow UI")
        print("2. Set up cron job for daily routine:")
        print("   30 16 * * 1-5 cd $(pwd) && python scripts/run_routine_mlflow.py --config config/online_config_mlflow.yaml >> data/logs/routine_mlflow.log 2>&1")
        print("3. Or run manually:")
        print("   python scripts/run_routine_mlflow.py --config config/online_config_mlflow.yaml")

    except Exception as e:
        print(f"\nFirst run failed: {e}")
        import traceback
        traceback.print_exc()

        # End MLflow run with FAILED status
        if hasattr(manager, 'mlflow_logger'):
            try:
                manager.mlflow_logger.end_run(status="FAILED")
            except:
                pass

        sys.exit(1)


if __name__ == "__main__":
    main()
