#!/usr/bin/env python
# Copyright (c) 2024
# Licensed under the MIT License.

"""
First Run Script - Initialize Online Manager

This script performs the initial setup and first training run for the online manager.

Usage:
    python first_run.py --config config/online_config.yaml
    python first_run.py --config config/online_config.yaml --reset
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
from src.managed_manager import ManagedOnlineManager


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
    # Initialize with default configuration
    python first_run.py

    # Reset existing data and reinitialize
    python first_run.py --reset

    # Use custom configuration
    python first_run.py --config config/my_config.yaml
        """
    )

    parser.add_argument(
        '--config',
        type=str,
        default='config/online_config.yaml',
        help='Path to configuration file (default: config/online_config.yaml)'
    )

    parser.add_argument(
        '--reset',
        action='store_true',
        help='Reset existing manager (delete checkpoint and models) before running'
    )

    parser.add_argument(
        '--log-dir',
        type=str,
        default='logs',
        help='Log directory (default: logs)'
    )

    args = parser.parse_args()

    # Load configuration
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Configuration file not found: {config_path}")
        print("\nPlease create a configuration file first:")
        print("  cp config/online_config_template.yaml config/online_config.yaml")
        print("  # Then edit config/online_config.yaml with your settings")
        sys.exit(1)

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Check if reset requested
    manager_path_str = config['online_manager'].get('manager_path', 'checkpoints/online_manager.pkl')
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

    qlib_config = config.get('qlib_config', {})
    provider_uri = qlib_config.get('provider_uri', '~/.qlib/qlib_data/cn_data')
    region = qlib_config.get('region', 'cn')

    qlib.init(provider_uri=provider_uri, region=region)
    print("Qlib initialized successfully")

    # Create manager and run first training
    print("\n" + "=" * 80)
    print("Creating Manager and Running First Training")
    print("=" * 80)

    try:
        manager = ManagedOnlineManager(
            config_path=str(config_path),
            log_dir=args.log_dir
        )

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
        print("   30 16 * * 1-5 cd $(pwd) && python scripts/run_routine.py --config config/online_config.yaml >> logs/routine.log 2>&1")
        print("3. Or run manually:")
        print("   python scripts/run_routine.py --config config/online_config.yaml")

    except Exception as e:
        print(f"\nFirst run failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
