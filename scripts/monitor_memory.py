#!/usr/bin/env python
# Copyright (c) 2024
# Licensed under the MIT License.

"""
Memory Monitor Script

Monitor memory usage during training and alert if approaching system limits.
Usage:
    python monitor_memory.py --pid <PID>
    python monitor_memory.py --command "python scripts/first_run.py"
"""

import argparse
import psutil
import time
import sys
import os
from datetime import datetime


def get_memory_info(pid=None):
    """Get memory information for a process or current system."""
    if pid:
        try:
            process = psutil.Process(pid)
            mem_info = process.memory_info()
            return {
                'rss': mem_info.rss / 1024 / 1024 / 1024,  # GB
                'vms': mem_info.vms / 1024 / 1024 / 1024,  # GB
                'percent': process.memory_percent(),
                'name': process.name(),
                'pid': pid
            }
        except psutil.NoSuchProcess:
            return None
    else:
        # System-wide memory
        mem = psutil.virtual_memory()
        return {
            'total': mem.total / 1024 / 1024 / 1024,  # GB
            'available': mem.available / 1024 / 1024 / 1024,  # GB
            'used': mem.used / 1024 / 1024 / 1024,  # GB
            'percent': mem.percent
        }


def format_memory.gb):
    """Format memory in GB."""
    if gb < 1:
        return f"{gb * 1024:.1f} MB"
    return f"{gb:.2f} GB"


def monitor_process(pid=None, interval=5, alert_threshold=85):
    """
    Monitor memory usage of a process.

    Args:
        pid: Process ID to monitor. If None, monitor system memory
        interval: Check interval in seconds
        alert_threshold: Alert if memory usage exceeds this percentage
    """
    print("=" * 80)
    print("MEMORY MONITOR")
    print("=" * 80)

    try:
        while True:
            mem = get_memory_info(pid)

            if mem is None:
                print(f"\nProcess {pid} no longer exists")
                break

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if pid:
                # Process memory
                print(f"\r[{timestamp}] PID {mem['pid']} ({mem['name']}): "
                      f"RSS: {format_memory(mem['rss'])} | "
                      f"VMS: {format_memory(mem['vms'])} | "
                      f"Mem%: {mem['percent']:.1f}%", end='')
            else:
                # System memory
                sys_mem = get_memory_info(None)
                print(f"\r[{timestamp}] System: "
                      f"Used: {format_memory(sys_mem['used'])} / "
                      f"{format_memory(sys_mem['total'])} "
                      f"({sys_mem['percent']:.1f}%) | "
                      f"Available: {format_memory(sys_mem['available'])}", end='')

                # Alert if system memory is low
                if sys_mem['percent'] >= alert_threshold:
                    print(f"\n\n⚠️  WARNING: System memory usage is {sys_mem['percent']:.1f}%!")
                    print("Consider stopping the process to avoid OOM Killer.")

            sys.stdout.flush()
            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n\nMonitoring stopped.")


def launch_and_monitor(command, interval=5):
    """Launch a command and monitor its memory usage."""
    print(f"Launching: {command}")
    print("=" * 80)

    # Launch the command
    import subprocess
    proc = subprocess.Popen(command, shell=True)
    pid = proc.pid

    print(f"Process started with PID: {pid}")
    print("Monitoring memory usage (Press Ctrl+C to stop monitoring)\n")

    # Monitor the process
    try:
        monitor_process(pid=pid, interval=interval)
    except KeyboardInterrupt:
        print("\n\nStopping monitored process...")
        proc.terminate()
        proc.wait()
        print("Process stopped.")


def main():
    parser = argparse.ArgumentParser(
        description="Monitor memory usage during training",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Monitor system memory
    python monitor_memory.py

    # Monitor a specific process
    python monitor_memory.py --pid 12345

    # Launch and monitor a command
    python monitor_memory.py --command "python scripts/first_run.py"
        """
    )

    parser.add_argument(
        '--pid',
        type=int,
        help='Process ID to monitor'
    )

    parser.add_argument(
        '--command',
        type=str,
        help='Command to launch and monitor'
    )

    parser.add_argument(
        '--interval',
        type=int,
        default=5,
        help='Check interval in seconds (default: 5)'
    )

    parser.add_argument(
        '--alert-threshold',
        type=int,
        default=85,
        help='Alert if system memory usage exceeds this %% (default: 85)'
    )

    args = parser.parse_args()

    if args.command:
        # Launch and monitor
        launch_and_monitor(args.command, args.interval)
    elif args.pid:
        # Monitor specific process
        monitor_process(pid=args.pid, interval=args.interval,
                       alert_threshold=args.alert_threshold)
    else:
        # Monitor system memory
        monitor_process(pid=None, interval=args.interval,
                       alert_threshold=args.alert_threshold)


if __name__ == "__main__":
    main()
