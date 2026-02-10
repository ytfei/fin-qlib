#!/usr/bin/env python
# Copyright (c) 2024
# Licensed under the MIT License.

"""
Cleanup temporary files and resources.

Usage:
    python cleanup_temp.py --all
    python cleanup_temp.py --joblib
    python cleanup_temp.py --mlflow
"""

import argparse
import shutil
import os
import sys
from pathlib import Path
import tempfile


def cleanup_joblib_temp():
    """Clean joblib temporary folders."""
    print("Cleaning joblib temporary files...")

    temp_dir = Path(tempfile.gettempdir())
    joblib_folders = list(temp_dir.glob("joblib_memmapping_folder_*"))

    if not joblib_folders:
        print("  No joblib temp folders found")
        return

    print(f"  Found {len(joblib_folders)} joblib temp folders")

    cleaned = 0
    for folder in joblib_folders:
        try:
            shutil.rmtree(folder)
            print(f"  ✓ Removed: {folder.name}")
            cleaned += 1
        except Exception as e:
            print(f"  ✗ Failed to remove {folder.name}: {e}")

    print(f"  Cleaned {cleaned}/{len(joblib_folders)} folders")


def cleanup_mlflow_runs(experiment_name=None):
    """Clean MLflow experiment runs (use with caution!)."""
    print("\nCleaning MLflow runs...")

    if experiment_name:
        confirm = input(f"  Delete ALL runs for experiment '{experiment_name}'? (yes/no): ")
        if confirm.lower() != 'yes':
            print("  Cancelled")
            return

    # Note: This is a placeholder - actual implementation depends on your MLflow setup
    print("  ⚠️  MLflow cleanup requires manual intervention")
    print("  Use 'mlflow ui' to view and delete experiments manually")


def cleanup_python_cache():
    """Clean Python cache files."""
    print("\nCleaning Python cache...")

    cache_count = 0
    for root, dirs, files in os.walk("."):
        # Skip .venv and .git
        if ".venv" in root or ".git" in root:
            continue

        # Remove __pycache__ directories
        if "__pycache__" in dirs:
            pycache_path = Path(root) / "__pycache__"
            try:
                shutil.rmtree(pycache_path)
                print(f"  ✓ Removed: {pycache_path}")
                cache_count += 1
            except Exception as e:
                print(f"  ✗ Failed: {pycache_path}: {e}")

        # Remove .pyc files
        for file in files:
            if file.endswith(".pyc"):
                pyc_path = Path(root) / file
                try:
                    pyc_path.unlink()
                    cache_count += 1
                except Exception:
                    pass

    print(f"  Cleaned {cache_count} cache items")


def cleanup_logs(days=7):
    """Clean old log files."""
    print(f"\nCleaning logs older than {days} days...")

    import time
    from datetime import timedelta

    log_dir = Path("logs")
    if not log_dir.exists():
        print("  No logs directory found")
        return

    cutoff_time = time.time() - (days * 86400)
    cleaned = 0

    for log_file in log_dir.glob("*.log"):
        if log_file.stat().st_mtime < cutoff_time:
            try:
                log_file.unlink()
                print(f"  ✓ Removed: {log_file.name}")
                cleaned += 1
            except Exception as e:
                print(f"  ✗ Failed: {log_file.name}: {e}")

    print(f"  Cleaned {cleaned} log files")


def main():
    parser = argparse.ArgumentParser(
        description="Cleanup temporary files and resources",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Clean everything
    python cleanup_temp.py --all

    # Clean only joblib temp
    python cleanup_temp.py --joblib

    # Clean logs older than 30 days
    python cleanup_temp.py --logs --days 30
        """
    )

    parser.add_argument(
        '--all',
        action='store_true',
        help='Clean all temporary files'
    )

    parser.add_argument(
        '--joblib',
        action='store_true',
        help='Clean joblib temporary folders'
    )

    parser.add_argument(
        '--cache',
        action='store_true',
        help='Clean Python cache (__pycache__, .pyc)'
    )

    parser.add_argument(
        '--logs',
        action='store_true',
        help='Clean old log files'
    )

    parser.add_argument(
        '--days',
        type=int,
        default=7,
        help='Log retention period in days (default: 7)'
    )

    parser.add_argument(
        '--mlflow',
        action='store_true',
        help='Clean MLflow runs (requires confirmation)'
    )

    args = parser.parse_args()

    if not any([args.all, args.joblib, args.cache, args.logs, args.mlflow]):
        parser.print_help()
        return

    print("=" * 80)
    print("CLEANUP TEMPORARY FILES")
    print("=" * 80)

    if args.all or args.joblib:
        cleanup_joblib_temp()

    if args.all or args.cache:
        cleanup_python_cache()

    if args.all or args.logs:
        cleanup_logs(days=args.days)

    if args.mlflow:
        cleanup_mlflow_runs()

    print("\n" + "=" * 80)
    print("CLEANUP COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
