#!/usr/bin/env python
# Copyright (c) 2024
# Licensed under the MIT License.

"""
Upgrade Strategy Script - Add new strategies to existing manager

Usage:
    python upgrade_strategy.py --config config/online_config.yaml --add XGB_Alpha158
    python upgrade_strategy.py --config config/online_config.yaml --disable LGB_Old
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
        description="Add, enable, or disable strategies in existing manager",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--config',
        type=str,
        default='config/online_config.yaml',
        help='Path to configuration file'
    )

    subparsers = parser.add_subparsers(dest='action', help='Action to perform')

    # Add action
    add_parser = subparsers.add_parser('add', help='Add new strategies from config')

    # Enable action
    enable_parser = subparsers.add_parser('enable', help='Enable a strategy')
    enable_parser.add_argument('name', type=str, help='Strategy name to enable')

    # Disable action
    disable_parser = subparsers.add_parser('disable', help='Disable a strategy')
    disable_parser.add_argument('name', type=str, help='Strategy name to disable')

    # List action
    list_parser = subparsers.add_parser('list', help='List all strategies')

    args = parser.parse_args()

    if args.action is None:
        parser.print_help()
        sys.exit(1)

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
    print(f"Loading manager from {args.config}...")
    manager = ManagedOnlineManager(config_path=str(config_path))

    if args.action == 'list':
        # List strategies
        print("\n" + "=" * 80)
        print("Strategies")
        print("=" * 80)

        for strategy in manager.manager.strategies:
            online_models = strategy.tool.online_models()
            status = "online" if len(online_models) > 0 else "offline"
            print(f"  {strategy.name_id}: {status} ({len(online_models)} models)")

    elif args.action == 'add':
        # Add strategies from config
        print("\n" + "=" * 80)
        print("Adding New Strategies")
        print("=" * 80)

        manager.sync_strategies()

        print("\nUpdated strategies:")
        for strategy in manager.manager.strategies:
            print(f"  - {strategy.name_id}")

    elif args.action == 'enable':
        # Enable strategy
        print(f"\nEnabling strategy: {args.name}")

        # Load config
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)

        # Find and enable strategy
        found = False
        for strategy in config_data['online_manager']['strategies']:
            if strategy['name'] == args.name:
                strategy['enabled'] = True
                found = True
                break

        if not found:
            print(f"Error: Strategy '{args.name}' not found in config")
            sys.exit(1)

        # Save updated config
        with open(config_path, 'w') as f:
            yaml.safe_dump(config_data, f, default_flow_style=False)

        print(f"Strategy '{args.name}' enabled in config")
        print("Run 'python upgrade_strategy.py --config config/online_config.yaml add' to activate")

    elif args.action == 'disable':
        # Disable strategy
        print(f"\nDisabling strategy: {args.name}")

        # Find strategy in manager and set to offline
        for strategy in manager.manager.strategies:
            if strategy.name_id == args.name:
                online_models = strategy.tool.online_models()
                if online_models:
                    strategy.tool.set_online_tag('offline', online_models)
                print(f"Strategy '{args.name}' set to offline")
                break
        else:
            print(f"Error: Strategy '{args.name}' not found in manager")
            sys.exit(1)

        # Also update config
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)

        for strategy in config_data['online_manager']['strategies']:
            if strategy['name'] == args.name:
                strategy['enabled'] = False
                break

        with open(config_path, 'w') as f:
            yaml.safe_dump(config_data, f, default_flow_style=False)

        print(f"Strategy '{args.name}' disabled in config")

    # Save manager
    if args.action in ['add', 'disable']:
        print("\nSaving manager...")
        manager._save_checkpoint()


if __name__ == "__main__":
    main()
