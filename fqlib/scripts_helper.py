# Copyright (c) 2024
# Licensed under the MIT License.

"""
Common utilities for fin-qlib scripts.

This module provides shared functionality for all scripts including:
- Project path resolution
- Configuration file handling
- Argument parsing helpers
"""

import os
import sys
from pathlib import Path
from typing import Optional
import argparse


def get_project_dir(project_arg: Optional[str] = None) -> Path:
    """
    Get the project directory.

    Args:
        project_arg: Project path from --project argument (optional)

    Returns:
        Path object pointing to the project directory
    """
    if project_arg:
        return Path(project_arg).resolve()

    # Default: use current working directory
    return Path.cwd()


def get_config_path(
    config_arg: Optional[str] = None,
    project_dir: Optional[Path] = None
) -> Path:
    """
    Get the configuration file path.

    Priority:
    1. Explicit --config argument
    2. <project_dir>/config/online_config.yaml

    Args:
        config_arg: Config path from --config argument (optional)
        project_dir: Project directory (optional)

    Returns:
        Path object pointing to the configuration file
    """
    if config_arg:
        return Path(config_arg).resolve()

    if project_dir:
        return project_dir / 'config' / 'online_config.yaml'

    # Default
    return Path.cwd() / 'config' / 'online_config.yaml'


def get_data_dir(project_dir: Optional[Path] = None) -> Path:
    """
    Get the data directory path.

    Args:
        project_dir: Project directory (optional)

    Returns:
        Path object pointing to the data directory
    """
    if project_dir:
        return project_dir / 'data'

    return Path.cwd() / 'data'


def get_log_dir(project_dir: Optional[Path] = None) -> Path:
    """
    Get the log directory path.

    Args:
        project_dir: Project directory (optional)

    Returns:
        Path object pointing to the log directory
    """
    if project_dir:
        return project_dir / 'data' / 'logs'

    return Path.cwd() / 'data' / 'logs'


def add_project_args(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """
    Add standard project-related arguments to an argument parser.

    This adds --project and --config arguments with proper defaults and help text.

    Args:
        parser: ArgumentParser to add arguments to

    Returns:
        The modified parser (for chaining)
    """
    parser.add_argument(
        '--project',
        type=str,
        default=None,
        help='Project root directory. If specified, config/ and data/ paths are relative to this directory. (default: current working directory)'
    )

    parser.add_argument(
        '--config',
        type=str,
        default=None,
        help='Path to configuration file. If not specified and --project is given, uses <project>/config/online_config.yaml. (default: config/online_config.yaml)'
    )

    return parser


def resolve_paths(args):
    """
    Resolve all paths from parsed arguments.

    This function should be called after parsing arguments with add_project_args().
    It resolves project_dir, config_path, data_dir, and log_dir based on the arguments.

    Args:
        args: Parsed arguments from argparse (must have 'project' and 'config' attributes)

    Returns:
        dict with keys: project_dir, config_path, data_dir, log_dir
    """
    # Resolve project directory
    project_dir = get_project_dir(args.project)

    # Resolve config path
    config_path = get_config_path(args.config, project_dir)

    # Resolve data and log directories
    data_dir = get_data_dir(project_dir)
    log_dir = get_log_dir(project_dir)

    return {
        'project_dir': project_dir,
        'config_path': config_path,
        'data_dir': data_dir,
        'log_dir': log_dir
    }


def validate_config(config_path: Path) -> bool:
    """
    Validate that the configuration file exists.

    Args:
        config_path: Path to configuration file

    Returns:
        True if config file exists, False otherwise
    """
    if not config_path.exists():
        print(f"Error: Configuration file not found: {config_path}")
        print()
        print("Please create a configuration file:")
        if config_path.name == 'online_config.yaml':
            print(f"  cp {config_path.parent / 'online_config_template.yaml'} {config_path}")
        print(f"  # Then edit {config_path} with your settings")
        return False

    return True


def setup_sys_path():
    """
    Add parent directory of scripts to sys.path.

    This allows scripts to import fqlib module.
    Should be called at the beginning of each script.
    """
    script_path = Path(__file__).resolve()

    # If we're in scripts/ directory, add parent
    if script_path.parent.name == 'scripts':
        sys.path.insert(0, str(script_path.parent.parent))
    else:
        # Add parent of this file's directory
        sys.path.insert(0, str(script_path.parent))


class ProjectPaths:
    """
    Helper class for managing project paths in scripts.

    Usage:
        >>> parser = argparse.ArgumentParser()
        >>> parser = add_project_args(parser)
        >>> args = parser.parse_args()
        >>> paths = ProjectPaths(args)
        >>> if paths.validate():
        ...     print(f"Project: {paths.project_dir}")
        ...     print(f"Config: {paths.config_path}")
    """

    def __init__(self, args, project_dir: Optional[Path] = None):
        """
        Initialize paths from parsed arguments.

        Args:
            args: Parsed arguments (must have 'project' and 'config' attributes)
            project_dir: Override project directory (optional)
        """
        self.project_dir = get_project_dir(args.project) if not project_dir else project_dir
        self.config_path = get_config_path(args.config, self.project_dir)
        self.data_dir = get_data_dir(self.project_dir)
        self.log_dir = get_log_dir(self.project_dir)

    def validate(self) -> bool:
        """Validate that required paths exist."""
        return validate_config(self.config_path)

    def __repr__(self) -> str:
        return (
            f"ProjectPaths(\n"
            f"  project_dir={self.project_dir},\n"
            f"  config_path={self.config_path},\n"
            f"  data_dir={self.data_dir},\n"
            f"  log_dir={self.log_dir}\n"
            f")"
        )
