# Copyright (c) 2024
# Licensed under the MIT License.

"""
Prediction service for handling backtest requests.

This module provides the core logic for generating stock predictions
using a trained ManagedOnlineManager.
"""

import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Tuple
import pandas as pd
from pandas import MultiIndex

import qlib
from qlib.workflow import R

from .managed_manager import ManagedOnlineManager


class PredictionService:
    """
    Service for generating stock predictions.

    This service wraps a ManagedOnlineManager and provides methods
    to query predictions for specific dates.

    Example:
        >>> service = PredictionService("config/online_config.yaml")
        >>> predictions = service.get_predictions("2025-01-10")
        >>> print(predictions.head())
    """

    def __init__(
        self,
        config_path: str = "config/online_config.yaml",
        log_dir: str = "data/logs"
    ):
        """
        Initialize the prediction service.

        Args:
            config_path: Path to the configuration file
            log_dir: Directory for log files
        """
        self.config_path = Path(config_path)
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Setup logging
        self.logger = self._setup_logging()

        # Initialize Qlib
        self._init_qlib()

        # Load manager
        self.manager = self._load_manager()

        self.logger.info("PredictionService initialized successfully")

    def _setup_logging(self) -> logging.Logger:
        """Setup logging for the prediction service."""
        logger = logging.getLogger("PredictionService")
        logger.setLevel(logging.INFO)

        # Clear existing handlers
        logger.handlers.clear()

        # Prevent propagation to root logger to avoid duplicate logs
        logger.propagate = False

        # File handler
        log_file = self.log_dir / f"prediction_service_{datetime.now():%Y%m%d}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        return logger

    def _init_qlib(self):
        """Initialize Qlib with configuration."""
        try:
            # Load config
            import yaml
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            qlib_config = config.get('qlib_config', {})

            # Initialize Qlib
            provider_uri = qlib_config.get('provider_uri', '~/.qlib/tushare_data/cn_data')
            region = qlib_config.get('region', 'cn')

            qlib.init(provider_uri=provider_uri, region=region)

            self.logger.info(f"Qlib initialized with provider_uri={provider_uri}, region={region}")

        except Exception as e:
            self.logger.error(f"Failed to initialize Qlib: {e}")
            raise

    def _load_manager(self) -> ManagedOnlineManager:
        """
        Load the ManagedOnlineManager.

        Returns:
            ManagedOnlineManager instance
        """
        try:
            manager = ManagedOnlineManager(
                config_path=str(self.config_path),
                log_dir=str(self.log_dir)
            )
            self.logger.info("ManagedOnlineManager loaded successfully")
            return manager

        except Exception as e:
            self.logger.error(f"Failed to load manager: {e}")
            raise

    def get_predictions(
        self,
        date: str,
        top_n: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Get predictions for a specific date.

        Args:
            date: Target date in YYYY-MM-DD format
            top_n: If specified, return only top N predictions

        Returns:
            DataFrame with predictions. Columns: instrument, score, (rank if top_n)

        Raises:
            ValueError: If date is not available
            Exception: If prediction retrieval fails
        """
        self.logger.info(f"Getting predictions for date: {date}")

        try:
            # Get signals from manager
            signals = self.manager.get_signals()

            if signals is None or len(signals) == 0:
                raise ValueError("No signals available in manager")

            # Filter by date
            if isinstance(signals.index, MultiIndex):
                # MultiIndex: (instrument, datetime)
                date_signals = signals[signals.index.get_level_values('datetime') == date]
            else:
                # Try to filter directly
                date_signals = signals.get(date, pd.Series())

            if date_signals is None or len(date_signals) == 0:
                raise ValueError(f"No predictions available for date: {date}")

            # Convert to DataFrame
            result_df = pd.DataFrame({
                'instrument': date_signals.index.get_level_values('instrument')
                if isinstance(date_signals.index, MultiIndex)
                else date_signals.index,
                'score': date_signals.values
            })

            # Sort by score (descending)
            result_df = result_df.sort_values('score', ascending=False).reset_index(drop=True)

            # Add rank if requested
            if top_n is not None:
                result_df = result_df.head(top_n)
                result_df['rank'] = range(1, len(result_df) + 1)

            self.logger.info(f"Retrieved {len(result_df)} predictions for {date}")

            return result_df

        except Exception as e:
            self.logger.error(f"Failed to get predictions for {date}: {e}")
            raise

    def get_available_dates(self) -> List[str]:
        """
        Get list of available prediction dates.

        Returns:
            List of dates in YYYY-MM-DD format
        """
        try:
            signals = self.manager.get_signals()

            if signals is None or len(signals) == 0:
                return []

            if isinstance(signals.index, MultiIndex):
                dates = signals.index.get_level_values('datetime').unique()
            else:
                dates = signals.index.unique()

            # Convert to string format
            date_strings = [str(d.date()) if hasattr(d, 'date') else str(d)
                           for d in dates]

            return sorted(date_strings)

        except Exception as e:
            self.logger.error(f"Failed to get available dates: {e}")
            return []

    def get_model_info(self) -> Dict:
        """
        Get information about loaded models.

        Returns:
            Dict with model information
        """
        try:
            status = self.manager.get_status()
            return status

        except Exception as e:
            self.logger.error(f"Failed to get model info: {e}")
            return {}

    def is_date_available(self, date: str) -> bool:
        """
        Check if predictions are available for a specific date.

        Args:
            date: Date in YYYY-MM-DD format

        Returns:
            True if predictions are available, False otherwise
        """
        try:
            available_dates = self.get_available_dates()
            return date in available_dates

        except Exception:
            return False

    def get_top_predictions(
        self,
        date: str,
        top_n: int = 10
    ) -> List[Tuple[str, float]]:
        """
        Get top N predictions for a specific date.

        Args:
            date: Target date in YYYY-MM-DD format
            top_n: Number of top predictions to return

        Returns:
            List of tuples (instrument, score)
        """
        try:
            df = self.get_predictions(date, top_n=top_n)

            return [(row['instrument'], row['score'])
                   for _, row in df.iterrows()]

        except Exception as e:
            self.logger.error(f"Failed to get top predictions for {date}: {e}")
            raise

    def batch_get_predictions(
        self,
        start_date: str,
        end_date: str,
        top_n: Optional[int] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        Get predictions for a date range.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            top_n: If specified, return only top N predictions per date

        Returns:
            Dict mapping date -> DataFrame of predictions
        """
        self.logger.info(f"Getting batch predictions from {start_date} to {end_date}")

        try:
            available_dates = self.get_available_dates()

            # Filter dates in range
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')

            filtered_dates = []
            for d in available_dates:
                try:
                    dt = datetime.strptime(d, '%Y-%m-%d')
                    if start_dt <= dt <= end_dt:
                        filtered_dates.append(d)
                except ValueError:
                    continue

            if not filtered_dates:
                self.logger.warning(f"No dates found in range {start_date} to {end_date}")
                return {}

            # Get predictions for each date
            results = {}
            for d in filtered_dates:
                try:
                    df = self.get_predictions(d, top_n=top_n)
                    results[d] = df
                except Exception as e:
                    self.logger.warning(f"Failed to get predictions for {d}: {e}")
                    continue

            self.logger.info(f"Retrieved predictions for {len(results)} dates")

            return results

        except Exception as e:
            self.logger.error(f"Failed to get batch predictions: {e}")
            raise
