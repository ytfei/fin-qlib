#!/usr/bin/env python
# Copyright (c) 2024
# Licensed under the MIT License.

"""
Get Signals Script - Export trading signals

Usage:
    python get_signals.py --config config/online_config.yaml
    python get_signals.py --config config/online_config.yaml --date 2024-01-15
    python get_signals.py --config config/online_config.yaml --top 30
"""

import argparse
import sys
import pandas as pd
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
import pickle
import qlib
from qlib.workflow.online.manager import OnlineManager


def main():
    parser = argparse.ArgumentParser(
        description="Export trading signals from Online Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--config',
        type=str,
        default='config/online_config.yaml',
        help='Path to configuration file'
    )

    parser.add_argument(
        '--manager-path',
        type=str,
        default=None,
        help='Path to manager checkpoint (overrides config)'
    )

    parser.add_argument(
        '--date',
        type=str,
        default=None,
        help='Get signals for specific date (YYYY-MM-DD). If not specified, uses latest.'
    )

    parser.add_argument(
        '--top',
        type=int,
        default=None,
        help='Show top N stocks only'
    )

    parser.add_argument(
        '--format',
        type=str,
        choices=['table', 'csv', 'json'],
        default='table',
        help='Output format'
    )

    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Output file (if not specified, prints to stdout)'
    )

    args = parser.parse_args()

    # Initialize Qlib
    config_path = Path(args.config)
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    qlib_config = config.get('qlib_config', {})
    qlib.init(
        provider_uri=qlib_config.get('provider_uri', '~/.qlib/qlib_data/cn_data'),
        region=qlib_config.get('region', 'cn')
    )

    # Load manager
    manager_path_str = args.manager_path or config['online_manager'].get('manager_path',
                                                                         'checkpoints/online_manager.pkl')
    manager_path = Path(manager_path_str)

    if not manager_path.exists():
        print(f"Error: Manager checkpoint not found: {manager_path}")
        print("\nPlease run first training first:")
        print("  python scripts/first_run.py --config config/online_config.yaml")
        sys.exit(1)

    print(f"Loading manager from {manager_path}...")
    manager = OnlineManager.load(manager_path)

    # Get signals
    signals = manager.get_signals()

    if signals is None:
        print("Error: No signals available. Please run routine first.")
        sys.exit(1)

    # Filter by date if specified
    if args.date:
        import pandas as pd
        target_date = pd.Timestamp(args.date)
        signals = signals[signals.index.get_level_values('datetime') == target_date]

        if len(signals) == 0:
            print(f"Error: No signals found for date {args.date}")
            print(f"Available dates: {signals.index.get_level_values('datetime').unique()}")
            sys.exit(1)
    else:
        # Get latest date's signals
        latest_date = signals.index.get_level_values('datetime').max()
        signals = signals[signals.index.get_level_values('datetime') == latest_date]
        print(f"Latest signals date: {latest_date}")

    # Apply top filter
    if args.top:
        if isinstance(signals, pd.DataFrame):
            signals = signals.iloc[:, 0].nlargest(args.top)
        else:
            signals = signals.nlargest(args.top)
        print(f"Showing top {args.top} stocks")

    # Format output
    if args.format == 'table':
        print("\n" + "=" * 80)
        print("Trading Signals")
        print("=" * 80)
        for stock, score in signals.items():
            if isinstance(score, pd.Series):
                score = score.iloc[0]
            print(f"{stock}: {score:.4f}")

    elif args.format == 'csv':
        output = signals.to_csv(args.output or sys.stdout)

    elif args.format == 'json':
        import json
        data = {}
        for stock, score in signals.items():
            if isinstance(score, pd.Series):
                score = score.iloc[0]
            data[stock] = float(score)

        output = json.dumps(data, indent=2)

        if args.output:
            with open(args.output, 'w') as f:
                f.write(output)
        else:
            print(output)

    print("\n" + "=" * 80)
    print(f"Total: {len(signals)} stocks")
    print("=" * 80)


if __name__ == "__main__":
    main()
