#!/usr/bin/env python
# Copyright (c) 2024
# Licensed under the MIT License.

"""
Online Manager Routine Script

This script is designed to be run by cron or other schedulers to execute
daily/weekly/monthly routine updates for the online trading models.

Usage:
    python run_routine.py --config config/online_config.yaml
    python run_routine.py --config config/online_config.yaml --cur_time 2024-01-15

Crontab example:
    # Run at 16:30 every weekday (Monday to Friday)
    30 16 * * 1-5 cd /path/to/fin-qlib && python scripts/run_routine.py --config config/online_config.yaml >> data/logs/routine.log 2>&1
"""

import argparse
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fqlib.managed_manager import ManagedOnlineManager
from fqlib.util import init_qlib_from_config


def main():
    parser = argparse.ArgumentParser(
        description="Run Online Manager routine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Use default configuration
    python run_routine.py

    # Specify configuration file
    python run_routine.py --config config/online_config.yaml

    # Run for specific date
    python run_routine.py --config config/online_config.yaml --cur_time 2024-01-15

    # Sync strategies before running
    python run_routine.py --config config/online_config.yaml --sync
        """
    )

    parser.add_argument(
        '--config',
        type=str,
        default='config/online_config.yaml',
        help='Path to configuration file (default: config/online_config.yaml)'
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
        default='data/logs',
        help='Log directory (default: logs)'
    )

    args = parser.parse_args()

    # Check if config file exists
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Configuration file not found: {config_path}")
        print(f"Please create a configuration file or use --config to specify one.")
        sys.exit(1)

    # Load configuration
    import yaml
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
        sys.exit(0)

    # Run routine
    print("\n" + "=" * 80)
    print("Running Routine")
    print("=" * 80)

    try:
        manager.run_routine(cur_time=args.cur_time)

        # Show final status
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

            # Remove duplicates if any
            if signals.index.duplicated().any():
                dup_count = signals.index.duplicated().sum()
                print(f"Warning: Found {dup_count} duplicate signals, removing...")
                signals = signals[~signals.index.duplicated(keep='first')]

            if isinstance(signals, pd.DataFrame):
                latest_date = signals.index.get_level_values('datetime').max()
                latest_signals = signals.loc[latest_date]
            else:
                latest_date = signals.index.get_level_values('datetime').max()
                latest_signals = signals.xs(latest_date, level='datetime')

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

    except Exception as e:
        print(f"\nRoutine failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("\n" + "=" * 80)
    print("Done!")
    print("=" * 80)


if __name__ == "__main__":
    import pandas as pd  # Import here for availability
    main()
