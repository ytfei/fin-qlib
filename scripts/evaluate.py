#!/usr/bin/env python
# Copyright (c) 2024
# Licensed under the MIT License.

"""
Evaluation Script - Compare strategy performance

Usage:
    python evaluate.py --config config/online_config.yaml --start 2023-01-01 --end 2024-01-01
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
import qlib
from fqlib.managed_manager import ManagedOnlineManager


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate and compare strategy performance",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--config',
        type=str,
        default='config/online_config.yaml',
        help='Path to configuration file'
    )

    parser.add_argument(
        '--start',
        type=str,
        required=True,
        help='Start date (YYYY-MM-DD)'
    )

    parser.add_argument(
        '--end',
        type=str,
        required=True,
        help='End date (YYYY-MM-DD)'
    )

    parser.add_argument(
        '--recommend',
        action='store_true',
        help='Show recommended ensemble method based on evaluation'
    )

    args = parser.parse_args()

    # Initialize Qlib
    print("Initializing Qlib...")
    config_path = Path(args.config)
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    qlib_config = config.get('qlib_config', {})
    qlib.init(
        provider_uri=qlib_config.get('provider_uri', '~/.qlib/qlib_data/cn_data'),
        region=qlib_config.get('region', 'cn')
    )

    # Load manager
    print(f"Loading manager from {args.config}...")
    manager = ManagedOnlineManager(config_path=str(config_path))

    # Evaluate
    print(f"\nEvaluating strategies from {args.start} to {args.end}...")
    print("=" * 80)

    try:
        manager.print_evaluation(args.start, args.end)

        if args.recommend:
            print("\n" + "=" * 80)
            print("Ensemble Method Recommendation")
            print("=" * 80)
            results = manager.evaluate_strategies(args.start, args.end)
            ensemble_method = manager.evaluator.recommend_ensemble_method(results)
            print(f"\nRecommended method: {type(ensemble_method).__name__}")
            print("\nTo use this method, update signal_config.ensemble_method in your config file")

    except Exception as e:
        print(f"\nEvaluation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
