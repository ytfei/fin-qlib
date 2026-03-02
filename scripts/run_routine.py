#!/usr/bin/env python
# Copyright (c) 2024
# Licensed under the MIT License.

"""
Online Manager Routine Script

This script is designed to be run by cron or other schedulers to execute
daily/weekly/monthly routine updates for the online trading models.

Usage:
    python run_routine.py
    python run_routine.py --project /path/to/project
    python run_routine.py --project /path/to/project --cur_time 2024-01-15

Crontab example:
    # Run at 16:30 every weekday (Monday to Friday)
    30 16 * * 1-5 cd /path/to/project && python scripts/run_routine.py >> data/logs/routine.log 2>&1
"""

import argparse
import sys
import os
from pathlib import Path

# Setup system path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fqlib.managed_manager import ManagedOnlineManager
from fqlib.util import init_qlib_from_config
from fqlib.scripts_helper import (
    add_project_args,
    resolve_paths,
    validate_config,
)


def main():
    parser = argparse.ArgumentParser(
        description="Run Online Manager routine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Use default project (current directory)
    python run_routine.py

    # Specify project directory
    python run_routine.py --project /path/to/project

    # Run for specific date
    python run_routine.py --project /path/to/project --cur_time 2024-01-15

    # Sync strategies before running
    python run_routine.py --project /path/to/project --sync

    # Use custom configuration (overrides project default)
    python run_routine.py --config config/my_config.yaml
        """
    )

    # Add standard project arguments
    parser = add_project_args(parser)

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
    import yaml
    with open(paths['config_path'], 'r') as f:
        config = yaml.safe_load(f)

    # Initialize Qlib
    print("=" * 80)
    print("Initializing Qlib")
    print("=" * 80)
    print(f"Project: {paths['project_dir']}")
    print(f"Config: {paths['config_path']}")

    init_qlib_from_config(config)

    # Create manager
    print("\n" + "=" * 80)
    print("Creating/Loading Manager")
    print("=" * 80)

    try:
        manager = ManagedOnlineManager(
            config_path=str(paths['config_path']),
            log_dir=str(log_dir),
            project_dir=str(paths['project_dir'])
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
