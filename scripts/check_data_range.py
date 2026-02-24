#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Check Qlib Data Range

This script checks the actual date range of your data and helps you
configure proper segments in your config file.

Usage:
    python scripts/check_data_range.py --config config/online_config.yaml
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
import qlib
import pandas as pd


def check_data_range(provider_uri: str, region: str):
    """
    Check the actual date range of the data.

    Args:
        provider_uri: Path to qlib data
        region: Region code (cn, us, etc.)
    """
    # Initialize Qlib
    qlib.init(provider_uri=provider_uri, region=region)

    print("=" * 80)
    print("Qlib Data Range Check")
    print("=" * 80)
    print(f"\nProvider URI: {provider_uri}")
    print(f"Region: {region}")

    try:
        from qlib.data import D

        # Get all instruments
        print("\nLoading instruments...")
        instruments = D.instruments(market='all')
        print(f"Total instruments: {len(instruments)}")
        print(f"Sample instruments: {list(instruments)[:5]}")

        # Get data for a sample instrument to check date range
        if instruments and len(instruments) > 0:
            # instruments is a list-like object, convert to list
            inst_list = list(instruments)
            sample_inst = inst_list[0]
            print(f"\nSample instrument: {sample_inst}")

            # Try to get the data
            data = D.features(
                instruments=[sample_inst],
                fields=["$close"],
                start_time="2020-01-01",
                end_time="2026-12-31"
            )

            if data is not None and len(data) > 0:
                # Get date range from multi-index
                dates = data.index.get_level_values('datetime')
                min_date = dates.min()
                max_date = dates.max()
                total_days = len(dates.unique())

                print(f"\n{'=' * 80}")
                print("Data Range Summary")
                print(f"{'=' * 80}")
                print(f"Earliest date: {min_date}")
                print(f"Latest date:   {max_date}")
                print(f"Total trading days: {total_days}")

                # Calculate recommended segments (80% train, 10% valid, 10% test)
                total_period = (max_date - min_date).days
                train_end = min_date + pd.Timedelta(days=int(total_period * 0.7))
                valid_end = min_date + pd.Timedelta(days=int(total_period * 0.85))

                print(f"\n{'=' * 80}")
                print("Recommended Segments Configuration")
                print(f"{'=' * 80}")
                print(f"train: [{min_date.strftime('%Y-%m-%d')}, {train_end.strftime('%Y-%m-%d')}]")
                print(f"valid: [{train_end.strftime('%Y-%m-%d')}, {valid_end.strftime('%Y-%m-%d')}]")
                print(f"test:  [{valid_end.strftime('%Y-%m-%d')}, {max_date.strftime('%Y-%m-%d')}]")

                # Check if current config is within range
                print(f"\n{'=' * 80}")
                print("Validation Notes")
                print(f"{'=' * 80}")
                print("✅ Your data ends at:", max_date.strftime('%Y-%m-%d'))
                print("⚠️  Make sure your config segments end BEFORE or ON this date")
                print("⚠️  The test end date should be <= ", max_date.strftime('%Y-%m-%d'))

            else:
                print("\n❌ No data found for the sample instrument.")
                print("Please check your data installation.")

    except Exception as e:
        print(f"\n❌ Error checking data range: {e}")
        import traceback
        traceback.print_exc()


def validate_config(config_path: str):
    """
    Validate that config segments are within data range.

    Args:
        config_path: Path to config file
    """
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    qlib_config = config.get('qlib_config', {})
    provider_uri = qlib_config.get('provider_uri', '~/.qlib/qlib_data/cn_data')
    region = qlib_config.get('region', 'cn')

    # Expand ~ in path
    provider_uri = Path(provider_uri).expanduser()

    # Check data range
    check_data_range(str(provider_uri), region)

    # Now check config segments
    print(f"\n{'=' * 80}")
    print("Config Segments Validation")
    print(f"{'=' * 80}")

    strategies = config['online_manager'].get('strategies', [])
    for strat in strategies:
        if not strat.get('enabled', True):
            continue

        name = strat.get('name', 'Unknown')
        print(f"\nStrategy: {name}")

        task_template = strat.get('task_template', {})
        dataset_config = task_template.get('dataset', {})
        segments = dataset_config.get('kwargs', {}).get('segments', {})

        if segments:
            print(f"  train: {segments.get('train')}")
            print(f"  valid: {segments.get('valid')}")
            print(f"  test:  {segments.get('test')}")


def main():
    parser = argparse.ArgumentParser(
        description="Check Qlib data range and validate config segments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Check data range with default config
    python scripts/check_data_range.py

    # Check with specific config
    python scripts/check_data_range.py --config config/online_config.yaml

    # Check only data range (no config validation)
    python scripts/check_data_range.py --provider-uri ~/.qlib/qlib_data/cn_data --region cn
        """
    )

    parser.add_argument(
        '--config',
        type=str,
        default='config/online_config.yaml',
        help='Path to configuration file (default: config/online_config.yaml)'
    )

    parser.add_argument(
        '--provider-uri',
        type=str,
        default=None,
        help='Qlib data provider URI (overrides config)'
    )

    parser.add_argument(
        '--region',
        type=str,
        default=None,
        help='Qlib region code (overrides config)'
    )

    args = parser.parse_args()

    # Check if config file exists
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Configuration file not found: {config_path}")
        sys.exit(1)

    if args.provider_uri:
        # Check only data range
        provider_uri = Path(args.provider_uri).expanduser()
        region = args.region or 'cn'
        check_data_range(str(provider_uri), region)
    else:
        # Validate config
        validate_config(str(config_path))


if __name__ == "__main__":
    main()
