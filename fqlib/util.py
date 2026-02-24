# Copyright (c) 2024
# Licensed under the MIT License.

"""
Utility functions for Qlib management.

This module provides common utility functions for initializing and configuring
Qlib for online trading operations.
"""

import qlib
from typing import Dict, Optional


def init_qlib_from_config(config: Dict, verbose: bool = True) -> None:
    """
    Initialize Qlib based on configuration dictionary.

    This function reads Qlib configuration from a dictionary and initializes
    Qlib with the appropriate settings for data provider, region, MLflow,
    MongoDB, and other services.

    Args:
        config: Configuration dictionary containing 'qlib_config' key.
                Expected structure:
                {
                    'qlib_config': {
                        'provider_uri': str,  # Path to qlib data
                        'region': str,        # 'cn', 'us', etc.
                        'mlflow_tracking_uri': Optional[str],
                        'mongo': {
                            'enabled': bool,
                            'task_url': str,
                            'task_db_name': str
                        },
                        'redis': {
                            'enabled': bool,
                            'host': str,
                            'port': int,
                            'db': int
                        }
                    }
                }
        verbose: Whether to print initialization messages (default: True).

    Raises:
        Exception: If Qlib initialization fails.

    Example:
        >>> import yaml
        >>> with open('config/online_config.yaml') as f:
        ...     config = yaml.safe_load(f)
        >>> init_qlib_from_config(config)
    """
    qlib_config = config.get('qlib_config', {})

    # Basic configuration
    provider_uri = qlib_config.get('provider_uri', '~/.qlib/qlib_data/cn_data')
    region = qlib_config.get('region', 'cn')

    # Build initialization kwargs
    init_kwargs = {
        'provider_uri': provider_uri,
        'region': region,
    }

    # MLflow configuration
    mlflow_uri = qlib_config.get('mlflow_tracking_uri')
    if mlflow_uri:
        init_kwargs['flask_server'] = True  # Enable MLflow
        init_kwargs['mlflow_tracking_uri'] = mlflow_uri
        if verbose:
            print(f"MLflow tracking URI: {mlflow_uri}")

    # MongoDB configuration
    mongo_config = qlib_config.get('mongo', {})
    if mongo_config.get('enabled', False):
        init_kwargs['mongo'] = {
            'task_url': mongo_config.get('task_url'),
            'task_db_name': mongo_config.get('task_db_name'),
        }
        if verbose:
            print(f"MongoDB enabled: {mongo_config['task_url']}")

    # Redis configuration (optional)
    redis_config = qlib_config.get('redis', {})
    if redis_config.get('enabled', False):
        # Redis configuration would be handled by custom cache
        if verbose:
            print(f"Redis enabled: {redis_config['host']}:{redis_config['port']}")

    # exp_manager configuration
    exp_manager_config = qlib_config.get('exp_manager', {})
    if exp_manager_config.get('enabled', False):
        init_kwargs['exp_manager'] = exp_manager_config
        if verbose:
            print(f"Experiment manager enabled: {exp_manager_config}")

    # Initialize Qlib
    try:
        qlib.init(**init_kwargs)
        if verbose:
            print("Qlib initialized successfully")
    except Exception as e:
        if verbose:
            print(f"Failed to initialize Qlib: {e}")
        raise


def load_config(config_path: str) -> Dict:
    """
    Load configuration from YAML file.

    Args:
        config_path: Path to YAML configuration file.

    Returns:
        Configuration dictionary.

    Raises:
        FileNotFoundError: If configuration file doesn't exist.
        yaml.YAMLError: If YAML parsing fails.

    Example:
        >>> config = load_config('config/online_config.yaml')
    """
    from pathlib import Path
    import yaml

    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_file, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)
