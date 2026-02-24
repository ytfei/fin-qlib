#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Quick Test Script - Minimal Configuration Test

This script runs a quick test with minimal configuration to verify
that the Qlib setup is working correctly.

Usage:
    python scripts/quick_test.py
    python scripts/quick_test.py --reset
"""

import argparse
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
import qlib
from fqlib.managed_manager import ManagedOnlineManager
from fqlib.util import init_qlib_from_config


def reset_checkpoints(manager_path: Path):
    """Remove existing checkpoint for clean test."""
    if manager_path.exists():
        print(f"Removing existing checkpoint: {manager_path}")
        os.remove(manager_path)
        print("✓ Checkpoint removed")
    else:
        print("✓ No existing checkpoint found")


def quick_test(config_path: str, reset: bool = False):
    """
    Run quick test with minimal configuration.

    Args:
        config_path: Path to minimal config file
        reset: Whether to reset existing checkpoints
    """
    print("=" * 80)
    print("Quick Test - Minimal Configuration")
    print("=" * 80)

    # Load configuration
    config_file = Path(config_path)
    if not config_file.exists():
        print(f"❌ Config file not found: {config_file}")
        sys.exit(1)

    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)

    # Reset if requested
    if reset:
        manager_path = Path(config['online_manager'].get('manager_path',
                                                         'data/checkpoints/online_manager_minimal.pkl'))
        reset_checkpoints(manager_path)

    # Initialize Qlib
    print("\n1️⃣  Initializing Qlib...")
    try:
        init_qlib_from_config(config)
        print("✓ Qlib initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize Qlib: {e}")
        sys.exit(1)

    # Create manager
    print("\n2️⃣  Creating Manager...")
    try:
        manager = ManagedOnlineManager(
            config_path=str(config_file),
            log_dir="data/logs"
        )
        print("✓ Manager created successfully")
    except Exception as e:
        print(f"❌ Failed to create manager: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Run first training
    print("\n3️⃣  Running First Training...")
    print("   (This may take a few minutes with minimal data)")
    try:
        manager.run_first_training(save_checkpoint=True)
        print("✓ First training completed successfully")
    except Exception as e:
        print(f"❌ First training failed: {e}")
        import traceback
        traceback.print_exc()

        # Provide helpful hints
        print("\n💡 Troubleshooting Tips:")
        print("   1. Check your data range:")
        print("      python scripts/simple_data_check.py")
        print("   2. Update config segments to match your data")
        print("   3. Make sure you have stock data installed")
        sys.exit(1)

    # Get status
    print("\n4️⃣  Checking Status...")
    try:
        status = manager.get_status()
        print(f"✓ Current time: {status['cur_time']}")
        print(f"✓ Strategies: {', '.join(status['strategies'])}")
        print(f"✓ Signals: {'YES' if status['signals_available'] else 'NO'}")

        if status['signals_available']:
            print(f"  - Signal count: {status['signal_count']}")
            print(f"  - Date range: {status['signal_start']} to {status['signal_end']}")
    except Exception as e:
        print(f"❌ Failed to get status: {e}")

    # Test routine
    print("\n5️⃣  Testing Routine...")
    try:
        manager.run_routine()
        print("✓ Routine completed successfully")
    except Exception as e:
        print(f"❌ Routine failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Final status
    print("\n6️⃣  Final Status...")
    manager.print_status()

    # Success!
    print("\n" + "=" * 80)
    print("✅ Quick Test PASSED!")
    print("=" * 80)
    print("\nNext Steps:")
    print("  1. Check generated signals:")
    print("     ls -lh data/signals/")
    print("  2. View logs:")
    print("     ls -lh data/logs/")
    print("  3. Run with full config:")
    print("     python scripts/first_run.py --config config/online_config.yaml")
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="Quick test with minimal configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run quick test
    python scripts/quick_test.py

    # Run with reset (clean slate)
    python scripts/quick_test.py --reset

    # Use custom config
    python scripts/quick_test.py --config config/my_minimal.yaml
        """
    )

    parser.add_argument(
        '--config',
        type=str,
        default='config/online_config_minimal.yaml',
        help='Path to minimal config (default: config/online_config_minimal.yaml)'
    )

    parser.add_argument(
        '--reset',
        action='store_true',
        help='Reset existing checkpoints before testing'
    )

    args = parser.parse_args()

    try:
        quick_test(args.config, args.reset)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
