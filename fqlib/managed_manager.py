# Copyright (c) 2024
# Licensed under the MIT License.

"""
Managed Online Manager with configuration-driven architecture.

This module provides a production-ready wrapper around Qlib's OnlineManager
with support for:
- YAML configuration
- Dynamic strategy addition/removal
- Hot reloading
- Signal ensemble methods
- Automatic checkpointing
"""

import os
import pickle
import yaml
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union, Callable
from datetime import datetime

import pandas as pd
import qlib
from qlib.workflow.online.manager import OnlineManager
from qlib.workflow.online.strategy import OnlineStrategy, RollingStrategy
from qlib.workflow.task.gen import RollingGen
from qlib.model.trainer import TrainerR, TrainerRM, DelayTrainerR, DelayTrainerRM
from qlib.workflow import R

from .ensemble import (
    WeightedEnsemble,
    BestModelEnsemble,
    DynamicWeightEnsemble,
    VotingEnsemble,
    AverageEnsemble,
    SignalEvaluator
)


class ManagedOnlineManager:
    """
    Configuration-driven Online Manager for production quant trading.

    Features:
    1. YAML-based configuration
    2. Dynamic strategy management (add/remove/update)
    3. Multiple ensemble methods
    4. Automatic checkpointing
    5. Signal export
    6. Performance logging

    Example:
        manager = ManagedOnlineManager("config/online_config.yaml")
        manager.sync_strategies()
        manager.run_routine()
    """

    def __init__(self, config_path: str, log_dir: str = "logs"):
        """
        Initialize ManagedOnlineManager from configuration file.

        Args:
            config_path: Path to YAML configuration file
            log_dir: Directory for log files
        """
        self.config_path = Path(config_path)
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Load configuration
        self.config = self._load_config()

        # Setup logging
        self.logger = self._setup_logging()

        # Initialize or load OnlineManager
        self.manager = self._load_or_create_manager()

        # Setup signal evaluator
        self.evaluator = SignalEvaluator(self.manager) if self.manager else None

    def _load_config(self) -> Dict:
        """Load YAML configuration file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        self._validate_config(config)
        return config

    def _validate_config(self, config: Dict):
        """Validate configuration structure."""
        required_keys = ['online_manager']
        for key in required_keys:
            if key not in config:
                raise ValueError(f"Missing required config key: {key}")

        if 'strategies' not in config['online_manager']:
            raise ValueError("Configuration must define at least one strategy")

    def _setup_logging(self) -> logging.Logger:
        """Setup logging with file and console handlers."""
        logger = logging.getLogger("ManagedOnlineManager")
        logger.setLevel(logging.INFO)

        # Clear existing handlers
        logger.handlers.clear()

        # File handler
        log_file = self.log_dir / f"online_manager_{datetime.now():%Y%m%d}.log"
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

    def _load_or_create_manager(self) -> OnlineManager:
        """
        Load existing OnlineManager from checkpoint or create new one.
        """
        manager_path = self.config['online_manager'].get('manager_path',
                                                          'checkpoints/online_manager.pkl')
        manager_path = Path(manager_path)

        # Ensure checkpoint directory exists
        manager_path.parent.mkdir(parents=True, exist_ok=True)

        if manager_path.exists():
            try:
                self.logger.info(f"Loading existing manager from {manager_path}")
                manager = pickle.load(open(manager_path, 'rb'))
                self.logger.info(f"Loaded manager with {len(manager.strategies)} strategies")
                self.logger.info(f"Current strategies: {[s.name_id for s in manager.strategies]}")
                return manager
            except Exception as e:
                self.logger.error(f"Failed to load manager: {e}. Creating new manager.")
                return self._create_manager()
        else:
            self.logger.info(f"No existing manager found. Creating new manager.")
            return self._create_manager()

    def _create_manager(self) -> OnlineManager:
        """Create new OnlineManager from configuration."""
        # Get enabled strategies
        enabled_strategies = self._create_strategies_from_config()

        if not enabled_strategies:
            raise ValueError("No enabled strategies in configuration")

        # Get trainer configuration
        trainer_config = self.config['online_manager'].get('trainer', {})
        trainer = self._create_trainer(trainer_config)

        # Create OnlineManager
        manager_config = self.config['online_manager']
        manager = OnlineManager(
            strategies=enabled_strategies,
            trainer=trainer,
            begin_time=manager_config.get('begin_time'),
            freq=manager_config.get('freq', 'day')
        )

        # Run first training
        self.logger.info("Running first training...")
        manager.first_train()
        self.logger.info("First training completed")

        # Initial save
        manager_path = manager_config.get('manager_path', 'checkpoints/online_manager.pkl')
        Path(manager_path).parent.mkdir(parents=True, exist_ok=True)
        manager.to_pickle(manager_path)
        self.logger.info(f"Manager saved to {manager_path}")

        return manager

    def _create_strategies_from_config(self) -> List[OnlineStrategy]:
        """Create strategy instances from configuration."""
        strategies = []
        strategy_configs = self.config['online_manager']['strategies']

        for strat_config in strategy_configs:
            if not strat_config.get('enabled', True):
                continue

            strategy = self._create_strategy(strat_config)
            strategies.append(strategy)

        return strategies

    def _create_strategy(self, config: Dict) -> OnlineStrategy:
        """
        Create a single strategy from configuration.

        Supports:
        - RollingStrategy (built-in)
        - Custom strategies via 'class' and 'module_path'
        """
        strategy_type = config.get('type', 'RollingStrategy')

        if strategy_type == 'RollingStrategy':
            return self._create_rolling_strategy(config)
        else:
            # Custom strategy
            return self._create_custom_strategy(config)

    def _create_rolling_strategy(self, config: Dict) -> RollingStrategy:
        """Create RollingStrategy from configuration."""
        name = config['name']
        task_template = config['task_template']

        # Rolling configuration
        rolling_config = config.get('rolling_config', {})
        rolling_step = rolling_config.get('step', 550)
        rolling_type = rolling_config.get('rtype', 'ROLL_SD')

        # Map string to RollingGen type
        rtype_map = {
            'ROLL_SD': RollingGen.ROLL_SD,
            'ROLL_EX': RollingGen.ROLL_EX,
        }
        rtype = rtype_map.get(rolling_type, RollingGen.ROLL_SD)

        rolling_gen = RollingGen(step=rolling_step, rtype=rtype)

        return RollingStrategy(
            name_id=name,
            task_template=task_template,
            rolling_gen=rolling_gen
        )

    def _create_custom_strategy(self, config: Dict) -> OnlineStrategy:
        """Create custom strategy class from configuration."""
        # Import custom strategy class
        module_path = config['module_path']
        class_name = config['class']

        try:
            from importlib import import_module
            module = import_module(module_path)
            StrategyClass = getattr(module, class_name)

            # Get init parameters
            init_params = config.get('init_params', {})
            init_params['name_id'] = config['name']

            return StrategyClass(**init_params)

        except Exception as e:
            raise ValueError(f"Failed to create custom strategy {class_name}: {e}")

    def _create_trainer(self, config: Dict):
        """Create trainer instance from configuration."""
        trainer_type = config.get('type', 'TrainerR')

        trainer_map = {
            'TrainerR': TrainerR,
            'TrainerRM': TrainerRM,
            'DelayTrainerR': DelayTrainerR,
            'DelayTrainerRM': DelayTrainerRM,
        }

        TrainerClass = trainer_map.get(trainer_type, TrainerR)
        return TrainerClass()

    def sync_strategies(self):
        """
        Synchronize strategies with configuration file.

        - Adds newly enabled strategies
        - Disables (sets to offline) strategies no longer in config
        """
        enabled_configs = [s for s in self.config['online_manager']['strategies']
                          if s.get('enabled', True)]
        enabled_names = {s['name'] for s in enabled_configs}
        current_names = {s.name_id for s in self.manager.strategies}

        # Add new strategies
        to_add = enabled_names - current_names
        if to_add:
            self.logger.info(f"Adding new strategies: {to_add}")
            new_strategies = []

            for strat_config in enabled_configs:
                if strat_config['name'] in to_add:
                    strategy = self._create_strategy(strat_config)
                    new_strategies.append(strategy)

            self.manager.add_strategy(new_strategies)
            self.logger.info(f"Added {len(new_strategies)} strategies")

        # Disable removed strategies
        to_disable = current_names - enabled_names
        if to_disable:
            self.logger.info(f"Disabling strategies: {to_disable}")
            for strategy in self.manager.strategies:
                if strategy.name_id in to_disable:
                    # Set all models to offline
                    online_models = strategy.tool.online_models()
                    if online_models:
                        strategy.tool.set_online_tag('offline', online_models)
                        self.logger.info(f"Disabled strategy '{strategy.name_id}'")

        # Update evaluator
        self.evaluator = SignalEvaluator(self.manager)

    def run_routine(self, cur_time: str = None,
                   task_kwargs: Dict = None,
                   model_kwargs: Dict = None,
                   signal_kwargs: Dict = None):
        """
        Execute routine: update predictions, train new models, prepare signals.

        Args:
            cur_time: Current time for routine. None for latest.
            task_kwargs: Additional kwargs for prepare_tasks
            model_kwargs: Additional kwargs for prepare_online_models
            signal_kwargs: Additional kwargs for prepare_signals
        """
        self.logger.info("=" * 80)
        self.logger.info("Starting routine")
        self.logger.info("=" * 80)

        task_kwargs = task_kwargs or {}
        model_kwargs = model_kwargs or {}
        signal_kwargs = signal_kwargs or {}

        # Execute routine
        try:
            self.manager.routine(
                cur_time=cur_time,
                task_kwargs=task_kwargs,
                model_kwargs=model_kwargs,
                signal_kwargs=signal_kwargs
            )
            self.logger.info("Routine completed successfully")
        except Exception as e:
            self.logger.error(f"Routine failed: {e}", exc_info=True)
            raise

        # Prepare signals with configured ensemble method
        prepare_func = self._get_ensemble_method()

        try:
            signals = self.manager.prepare_signals(prepare_func=prepare_func)
            self.logger.info(f"Generated {len(signals)} signals")
            self.logger.info(f"Signal date range: {signals.index.get_level_values('datetime').min()} "
                           f"to {signals.index.get_level_values('datetime').max()}")
        except Exception as e:
            self.logger.error(f"Failed to prepare signals: {e}", exc_info=True)
            raise

        # Save checkpoint
        self._save_checkpoint()

        # Export signals
        self._export_signals(signals)

    def _get_ensemble_method(self) -> Callable:
        """Get ensemble method from configuration."""
        signal_config = self.config['online_manager'].get('signal_config', {})
        method = signal_config.get('ensemble_method', 'average')

        method_map = {
            'average': AverageEnsemble(),
            'weighted': WeightedEnsemble(signal_config.get('weights', {})),
            'best': BestModelEnsemble(signal_config.get('best_strategy')),
            'dynamic': DynamicWeightEnsemble(
                signal_config.get('lookback_days', 30),
                signal_config.get('metric', 'ic')
            ),
            'voting': VotingEnsemble(
                signal_config.get('top_n', 50),
                signal_config.get('min_votes'),
                signal_config.get('return_type', 'weighted')
            ),
        }

        ensemble_func = method_map.get(method, AverageEnsemble())
        self.logger.info(f"Using ensemble method: {method}")

        return ensemble_func

    def _save_checkpoint(self):
        """Save manager checkpoint."""
        manager_path = self.config['online_manager'].get('manager_path',
                                                          'checkpoints/online_manager.pkl')
        self.manager.to_pickle(manager_path)
        self.logger.info(f"Checkpoint saved to {manager_path}")

    def _export_signals(self, signals: Union[pd.Series, pd.DataFrame]):
        """Export signals to file."""
        export_config = self.config['online_manager'].get('signal_export', {})

        if not export_config.get('enabled', True):
            return

        # Export directory
        export_dir = Path(export_config.get('dir', 'signals'))
        export_dir.mkdir(parents=True, exist_ok=True)

        # Export format
        export_format = export_config.get('format', 'csv')

        # Get latest date for filename
        if isinstance(signals, pd.DataFrame):
            latest_date = signals.index.get_level_values('datetime').max()
        else:
            latest_date = signals.index.get_level_values('datetime').max()

        date_str = latest_date.strftime('%Y%m%d')

        if export_format == 'csv':
            output_path = export_dir / f"signals_{date_str}.csv"
            signals.to_csv(output_path)
            self.logger.info(f"Signals exported to {output_path}")

        elif export_format == 'parquet':
            output_path = export_dir / f"signals_{date_str}.parquet"
            signals.to_parquet(output_path)
            self.logger.info(f"Signals exported to {output_path}")

        # Export latest signals
        if export_config.get('export_latest', True):
            latest_path = export_dir / "signals_latest.csv"
            signals.to_csv(latest_path)
            self.logger.info(f"Latest signals exported to {latest_path}")

    def get_signals(self) -> Union[pd.Series, pd.DataFrame]:
        """Get current signals."""
        return self.manager.get_signals()

    def get_online_models(self):
        """Get all online models across all strategies."""
        models = {}
        for strategy in self.manager.strategies:
            models[strategy.name_id] = strategy.tool.online_models()
        return models

    def evaluate_strategies(self, start_date: str, end_date: str) -> Dict:
        """
        Evaluate all strategies over given date range.

        Returns:
            Dict mapping strategy_name -> metrics
        """
        if self.evaluator is None:
            self.evaluator = SignalEvaluator(self.manager)

        results = self.evaluator.evaluate_all(start_date, end_date)
        return results

    def print_evaluation(self, start_date: str, end_date: str):
        """Print strategy evaluation comparison."""
        results = self.evaluate_strategies(start_date, end_date)
        self.evaluator.print_comparison(results)

        # Recommend ensemble method
        ensemble_method = self.evaluator.recommend_ensemble_method(results)
        print(f"\nRecommended ensemble method: {type(ensemble_method).__name__}")

    def get_status(self) -> Dict:
        """
        Get current manager status.

        Returns:
            Dict with status information
        """
        status = {
            'n_strategies': len(self.manager.strategies),
            'strategies': [s.name_id for s in self.manager.strategies],
            'cur_time': str(self.manager.cur_time),
            'signals_available': self.manager.signals is not None,
        }

        if self.manager.signals is not None:
            signals = self.manager.signals
            status['signal_count'] = len(signals)
            status['signal_start'] = str(signals.index.get_level_values('datetime').min())
            status['signal_end'] = str(signals.index.get_level_values('datetime').max())

        return status

    def print_status(self):
        """Print formatted status information."""
        status = self.get_status()

        print("\n" + "=" * 80)
        print("Online Manager Status")
        print("=" * 80)
        print(f"Current time: {status['cur_time']}")
        print(f"Number of strategies: {status['n_strategies']}")
        print(f"Strategies: {', '.join(status['strategies'])}")

        if status['signals_available']:
            print(f"\nSignals: YES")
            print(f"  Signal count: {status['signal_count']}")
            print(f"  Date range: {status['signal_start']} to {status['signal_end']}")
        else:
            print(f"\nSignals: NO")

        print("=" * 80)
