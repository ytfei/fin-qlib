#!/usr/bin/env python
# Copyright (c) 2024
# Licensed under the MIT License.

"""
Script to start the FastAPI backtest service server.

Usage:
    python scripts/start_api_server.py
    python scripts/start_api_server.py --project /path/to/project
    python scripts/start_api_server.py --port 8080

Environment Variables (optional):
    API_TOKEN: API authentication token (default: empty/disabled)
    API_HOST: Server host (default: 0.0.0.0)
    API_PORT: Server port (default: 8000)
    API_WORKERS: Number of worker processes (default: 1)
"""

import os
import sys
import logging
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import uvicorn
from fqlib.scripts_helper import (
    add_project_args,
    resolve_paths,
    validate_config,
)


def main():
    """Main entry point for starting the API server."""

    parser = argparse.ArgumentParser(
        description="Start the Stock Prediction Backtest API Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Start with default settings (current directory)
    python scripts/start_api_server.py

    # Start with specific project
    python scripts/start_api_server.py --project /path/to/project

    # Start on custom port
    python scripts/start_api_server.py --project /path/to/project --port 8080
        """
    )

    # Add standard project arguments
    parser = add_project_args(parser)

    parser.add_argument(
        '--host',
        type=str,
        default=None,
        help='Server host (default: 0.0.0.0, or API_HOST env var)'
    )

    parser.add_argument(
        '--port',
        type=int,
        default=None,
        help='Server port (default: 8000, or API_PORT env var)'
    )

    parser.add_argument(
        '--workers',
        type=int,
        default=None,
        help='Number of worker processes (default: 1, or API_WORKERS env var)'
    )

    parser.add_argument(
        '--log-dir',
        type=str,
        default=None,
        help='Log directory (default: <project>/data/logs)'
    )

    args = parser.parse_args()

    # Resolve paths
    paths = resolve_paths(args)

    # Override log_dir if explicitly provided
    if args.log_dir:
        log_dir = Path(args.log_dir)
    else:
        log_dir = paths['log_dir']

    # Get configuration from environment or defaults
    host = args.host or os.getenv('API_HOST', '0.0.0.0')
    port = args.port or int(os.getenv('API_PORT', '8000'))
    workers = args.workers or int(os.getenv('API_WORKERS', '1'))

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
    logger.info(f"Project: {paths['project_dir']}")
    logger.info(f"Configuration:")
    logger.info(f"  Config path: {paths['config_path']}")
    logger.info(f"  Log directory: {log_dir}")
    logger.info(f"Server:")
    logger.info(f"  Host: {host}")
    logger.info(f"  Port: {port}")
    logger.info(f"  Workers: {workers}")

    # Check authentication status
    api_token = os.getenv('API_TOKEN', '')
    if api_token:
        logger.info(f"  🔒 Authentication: ENABLED")
    else:
        logger.info(f"  ⚠️  Authentication: DISABLED")

    logger.info("=" * 80)

    # Validate config
    if not validate_config(paths['config_path']):
        sys.exit(1)

    # Set environment variables for api_server
    os.environ['CONFIG_PATH'] = str(paths['config_path'])
    os.environ['LOG_DIR'] = str(log_dir)
    os.environ['PROJECT_DIR'] = str(paths['project_dir'])

    # Start server
    try:
        logger.info("Starting uvicorn server...")
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
