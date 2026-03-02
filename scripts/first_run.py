#!/usr/bin/env python
# Copyright (c) 2024
# Licensed under the MIT License.

"""
First Run Script - Initialize Online Manager

This script performs the initial setup and first training run for the online manager.

Usage:
    python first_run.py
    python first_run.py --project /path/to/project
    python first_run.py --project /path/to/project --reset
"""

import argparse
import sys
import os
import shutil
from pathlib import Path

# Setup system path
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
import qlib
from fqlib.managed_manager import ManagedOnlineManager
from fqlib.util import init_qlib_from_config
from fqlib.scripts_helper import (
    add_project_args,
    resolve_paths,
    validate_config,
)


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
    # NOTE: This requires additional implementation

    print("Reset complete!")


def main():
    parser = argparse.ArgumentParser(
        description="Initialize Online Manager and run first training",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Initialize with default project (current directory)
    python first_run.py

    # Initialize with specific project
    python first_run.py --project /path/to/project

    # Reset existing data and reinitialize
    python first_run.py --project /path/to/project --reset

    # Use custom configuration (overrides project default)
    python first_run.py --config config/my_config.yaml
        """
    )

    # Add standard project arguments
    parser = add_project_args(parser)

    parser.add_argument(
        '--reset',
        action='store_true',
        help='Reset existing manager (delete checkpoint and models) before running'
    )

    parser.add_argument(
        '--log-dir',
        type=str,
        default=None,
        help='Log directory (default: <project>/data/logs)'
    )

    args = parser.parse_args()

    # Resolve paths
    paths = resolve_paths(args)

    # Override log_dir if explicitly provided
    if args.log_dir:
        log_dir = Path(args.log_dir)
    else:
        log_dir = paths['log_dir']

    # Validate config
    if not validate_config(paths['config_path']):
        sys.exit(1)

    # Load configuration
    with open(paths['config_path'], 'r') as f:
        config = yaml.safe_load(f)

    # Check if reset requested
    manager_path_str = config['online_manager'].get('manager_path', 'data/checkpoints/online_manager.pkl')
    # Resolve manager path relative to project
    manager_path = paths['project_dir'] / manager_path_str

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
    print(f"Project: {paths['project_dir']}")
    print(f"Config: {paths['config_path']}")

    init_qlib_from_config(config)

    # Create manager (strategies are initialized but not trained yet)
    print("\n" + "=" * 80)
    print("Creating Manager")
    print("Strategies initialized. First training will be executed separately...")
    print("=" * 80)

    try:
        manager = ManagedOnlineManager(
            config_path=str(paths['config_path']),
            log_dir=str(log_dir),
            project_dir=str(paths['project_dir'])
        )

        print("\n" + "=" * 80)
        print("Manager Created Successfully!")
        print("=" * 80)

        # Run first training
        print("\n" + "=" * 80)
        print("Running First Training")
        print("=" * 80)

        manager.run_first_training()

        print("\n" + "=" * 80)
        print("First Training Completed Successfully!")
        print("=" * 80)

        # Show status
        manager.print_status()

        print("\n" + "=" * 80)
        print("Next Steps:")
        print("=" * 80)
        print("1. Review the trained models and predictions")
        print("2. Set up cron job for daily routine:")
        print(f"   30 16 * * 1-5 cd {paths['project_dir']} && python scripts/run_routine.py --project {paths['project_dir']} >> {log_dir}/routine.log 2>&1")
        print("3. Or run manually:")
        print(f"   python scripts/run_routine.py --project {paths['project_dir']}")

    except Exception as e:
        print(f"\nFirst run failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
