#!/usr/bin/env python
# Copyright (c) 2024
# Licensed under the MIT License.

"""
Script to start the FastAPI backtest service server.

Usage:
    python scripts/start_api_server.py

Environment Variables (optional):
    CONFIG_PATH: Path to configuration file (default: config/online_config.yaml)
    LOG_DIR: Directory for log files (default: data/logs)
    API_HOST: Server host (default: 0.0.0.0)
    API_PORT: Server port (default: 8000)
    API_WORKERS: Number of worker processes (default: 1)
"""

import os
import sys
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uvicorn


def main():
    """Main entry point for starting the API server."""

    # Get configuration from environment
    config_path = os.getenv('CONFIG_PATH', 'config/online_config.yaml')
    log_dir = os.getenv('LOG_DIR', 'data/logs')
    host = os.getenv('API_HOST', '0.0.0.0')
    port = int(os.getenv('API_PORT', '8000'))
    workers = int(os.getenv('API_WORKERS', '1'))

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    # Print configuration
    logger.info("=" * 80)
    logger.info("Starting Stock Prediction Backtest API Server")
    logger.info("=" * 80)
    logger.info(f"Configuration:")
    logger.info(f"  Config path: {config_path}")
    logger.info(f"  Log directory: {log_dir}")
    logger.info(f"  Host: {host}")
    logger.info(f"  Port: {port}")
    logger.info(f"  Workers: {workers}")
    logger.info("=" * 80)

    # Check if config file exists
    if not os.path.exists(config_path):
        logger.error(f"Configuration file not found: {config_path}")
        logger.error("Please create a configuration file or set CONFIG_PATH environment variable")
        sys.exit(1)

    # Start server
    try:
        uvicorn.run(
            "fqlib.api_server:app",
            host=host,
            port=port,
            workers=workers,
            reload=False,
            log_level="info"
        )
    except Exception as e:
        logger.error(f"Failed to start server: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
