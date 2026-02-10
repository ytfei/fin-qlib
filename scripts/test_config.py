#!/usr/bin/env python
# Copyright (c) 2024
# Licensed under the MIT License.

"""
Configuration Test Script

This script validates the configuration file without running any training.
Useful for debugging configuration issues.

Usage:
    python scripts/test_config.py --config config/online_config.yaml
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml


def test_config(config_path: str):
    """Validate configuration file."""

    print("=" * 80)
    print("Configuration Test")
    print("=" * 80)

    # Check if file exists
    config_file = Path(config_path)
    if not config_file.exists():
        print(f"❌ Configuration file not found: {config_path}")
        return False

    print(f"✓ Configuration file exists: {config_path}")

    # Load YAML
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        print(f"✓ YAML is valid")
    except Exception as e:
        print(f"❌ YAML parsing failed: {e}")
        return False

    # Validate structure
    required_keys = ['online_manager']
    for key in required_keys:
        if key not in config:
            print(f"❌ Missing required key: {key}")
            return False
        print(f"✓ Key exists: {key}")

    # Validate online_manager section
    om_config = config['online_manager']

    # Check strategies
    if 'strategies' not in om_config:
        print(f"❌ No strategies defined")
        return False

    strategies = om_config['strategies']
    enabled_strategies = [s for s in strategies if s.get('enabled', True)]

    if len(enabled_strategies) == 0:
        print(f"⚠️  Warning: No enabled strategies")
    else:
        print(f"✓ Found {len(enabled_strategies)} enabled strategy(ies)")

    for strat in enabled_strategies:
        name = strat.get('name', 'unnamed')
        strat_type = strat.get('type', 'RollingStrategy')
        print(f"  - {name} ({strat_type})")

        # Check task template
        if 'task_template' not in strat:
            print(f"    ❌ Missing task_template")
            return False

        task = strat['task_template']

        # Check model
        if 'model' not in task:
            print(f"    ❌ Missing model configuration")
            return False

        model = task['model']
        if 'class' not in model:
            print(f"    ❌ Missing model class")
            return False
        print(f"    ✓ Model: {model['class']}")

        # Check dataset
        if 'dataset' not in task:
            print(f"    ❌ Missing dataset configuration")
            return False

        dataset = task['dataset']
        if 'class' not in dataset:
            print(f"    ❌ Missing dataset class")
            return False
        print(f"    ✓ Dataset: {dataset['class']}")

        # Check segments
        if 'kwargs' not in dataset:
            print(f"    ❌ Missing dataset kwargs")
            return False

        ds_kwargs = dataset['kwargs']
        if 'segments' not in ds_kwargs:
            print(f"    ❌ Missing data segments")
            return False

        segments = ds_kwargs['segments']
        for seg_name in ['train', 'valid', 'test']:
            if seg_name not in segments:
                print(f"    ⚠️  Warning: Missing {seg_name} segment")
            else:
                seg = segments[seg_name]
                if isinstance(seg, (list, tuple)) and len(seg) == 2:
                    print(f"    ✓ {seg_name.capitalize()}: {seg[0]} to {seg[1]}")
                else:
                    print(f"    ⚠️  Warning: Invalid {seg_name} segment format")

    # Check signal config
    if 'signal_config' in om_config:
        sig_config = om_config['signal_config']
        ensemble_method = sig_config.get('ensemble_method', 'average')
        print(f"✓ Signal ensemble method: {ensemble_method}")

        if ensemble_method == 'weighted':
            if 'weights' not in sig_config:
                print(f"    ⚠️  Warning: Weighted ensemble but no weights defined")
            else:
                weights = sig_config['weights']
                total = sum(weights.values())
                if abs(total - 1.0) > 0.01:
                    print(f"    ⚠️  Warning: Weights sum to {total}, should be 1.0")
                else:
                    print(f"    ✓ Weights sum to {total:.2f}")

    # Check qlib config
    if 'qlib_config' in config:
        qlib_config = config['qlib_config']
        provider_uri = qlib_config.get('provider_uri', '~/.qlib/qlib_data/cn_data')
        region = qlib_config.get('region', 'cn')
        print(f"✓ Qlib config: region={region}, provider={provider_uri}")

    # Check trainer
    if 'trainer' in om_config:
        trainer_config = om_config['trainer']
        trainer_type = trainer_config.get('type', 'TrainerR')
        print(f"✓ Trainer type: {trainer_type}")

    # Print summary
    print("\n" + "=" * 80)
    print("Configuration Test Summary")
    print("=" * 80)
    print(f"✓ Configuration is valid!")
    print(f"  - {len(enabled_strategies)} strategy(ies) enabled")
    print(f"  - Ensemble method: {om_config.get('signal_config', {}).get('ensemble_method', 'average')}")
    print("\nNext steps:")
    print("  1. Run first training: python scripts/first_run.py --config config/online_config.yaml")
    print("  2. Set up cron job for daily routine")

    return True


def main():
    parser = argparse.ArgumentParser(description="Test configuration file")
    parser.add_argument(
        '--config',
        type=str,
        default='config/online_config.yaml',
        help='Path to configuration file'
    )

    args = parser.parse_args()

    success = test_config(args.config)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
