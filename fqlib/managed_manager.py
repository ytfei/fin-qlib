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
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union, Callable
from datetime import datetime
from pprint import pformat

import pandas as pd
from pandas import MultiIndex
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

    def __init__(self, config_path: str, log_dir: str = "data/logs"):
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

        # Prevent duplicate logging
        logger.propagate = False

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
                                                          'data/checkpoints/online_manager.pkl')
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

        # Log pending tasks (before training)
        self._log_pending_tasks(enabled_strategies, trainer, manager_config)

        # NOTE: first_train() is NOT called here.
        # It should be explicitly called by the user via run_first_training() method.
        # This allows for better control and separation of concerns.

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

    def _log_pending_tasks(self, strategies: List[OnlineStrategy], trainer, manager_config: Dict):
        """
        Log pending tasks and their configurations before training.

        This method records:
        - Task configurations for each strategy
        - Model and dataset parameters
        - Recorder configurations
        - Rolling configurations
        - Saves to both log file and JSON file for reference

        Args:
            strategies: List of OnlineStrategy instances
            trainer: Trainer instance
            manager_config: Manager configuration dict
        """
        self.logger.info("=" * 80)
        self.logger.info("PENDING TASKS CONFIGURATION")
        self.logger.info("=" * 80)

        # Collect task information
        tasks_info = {
            "timestamp": datetime.now().isoformat(),
            "trainer_type": type(trainer).__name__,
            "trainer_config": manager_config.get('trainer', {}),
            "manager_config": {
                "begin_time": manager_config.get('begin_time'),
                "freq": manager_config.get('freq', 'day'),
                "manager_path": manager_config.get('manager_path', 'data/checkpoints/online_manager.pkl'),
            },
            "strategies": []
        }

        for strategy in strategies:
            strat_name = strategy.name_id
            self.logger.info(f"\n{'=' * 60}")
            self.logger.info(f"Strategy: {strat_name}")
            self.logger.info(f"{'=' * 60}")

            # Get task template
            task_template = strategy.task_template

            strat_info = {
                "name": strat_name,
                "type": type(strategy).__name__,
                "task_template": {}
            }

            # Model configuration
            if 'model' in task_template:
                model_config = task_template['model']
                self.logger.info(f"\n[Model]")
                self.logger.info(f"  Class: {model_config.get('class')}")
                self.logger.info(f"  Module: {model_config.get('module_path')}")
                self.logger.info(f"  Parameters:")
                for key, value in model_config.get('kwargs', {}).items():
                    self.logger.info(f"    {key}: {value}")

                strat_info["task_template"]["model"] = model_config

            # Dataset configuration
            if 'dataset' in task_template:
                dataset_config = task_template['dataset']
                self.logger.info(f"\n[Dataset]")
                self.logger.info(f"  Class: {dataset_config.get('class')}")
                self.logger.info(f"  Module: {dataset_config.get('module_path')}")

                # Log segments
                if 'kwargs' in dataset_config and 'segments' in dataset_config['kwargs']:
                    segments = dataset_config['kwargs']['segments']
                    self.logger.info(f"  Segments:")
                    for seg_type, seg_range in segments.items():
                        self.logger.info(f"    {seg_type}: {seg_range}")

                # Log handler
                if 'kwargs' in dataset_config and 'handler' in dataset_config['kwargs']:
                    handler = dataset_config['kwargs']['handler']
                    self.logger.info(f"  Handler:")
                    self.logger.info(f"    Class: {handler.get('class')}")
                    self.logger.info(f"    Module: {handler.get('module_path')}")

                strat_info["task_template"]["dataset"] = dataset_config

            # Recorder configuration
            if 'recorder' in task_template:
                recorder_config = task_template['recorder']
                self.logger.info(f"\n[Recorder]")
                if isinstance(recorder_config, list):
                    self.logger.info(f"  Count: {len(recorder_config)}")
                    for i, rec in enumerate(recorder_config):
                        self.logger.info(f"  [{i}] Class: {rec.get('class')}")
                        self.logger.info(f"      Module: {rec.get('module_path')}")
                else:
                    self.logger.info(f"  Class: {recorder_config.get('class')}")
                    self.logger.info(f"  Module: {recorder_config.get('module_path')}")

                strat_info["task_template"]["recorder"] = recorder_config

            # Rolling configuration
            if hasattr(strategy, 'rolling_gen'):
                rolling_gen = strategy.rolling_gen
                self.logger.info(f"\n[Rolling]")
                self.logger.info(f"  Step: {rolling_gen.step}")
                self.logger.info(f"  Type: {rolling_gen.rtype}")

                strat_info["rolling"] = {
                    "step": rolling_gen.step,
                    "rtype": rolling_gen.rtype
                }

            tasks_info["strategies"].append(strat_info)

        # Summary
        self.logger.info(f"\n{'=' * 80}")
        self.logger.info(f"SUMMARY")
        self.logger.info(f"{'=' * 80}")
        self.logger.info(f"Total Strategies: {len(strategies)}")
        self.logger.info(f"Trainer: {type(trainer).__name__}")
        self.logger.info(f"Frequency: {manager_config.get('freq', 'day')}")
        self.logger.info(f"Begin Time: {manager_config.get('begin_time', 'latest')}")
        self.logger.info(f"{'=' * 80}\n")

        # Save to JSON file for reference
        tasks_dir = self.log_dir / "tasks"
        tasks_dir.mkdir(parents=True, exist_ok=True)
        tasks_file = tasks_dir / f"pending_tasks_{datetime.now():%Y%m%d_%H%M%S}.json"

        with open(tasks_file, 'w', encoding='utf-8') as f:
            json.dump(tasks_info, f, indent=2, ensure_ascii=False, default=str)

        self.logger.info(f"Task configuration saved to: {tasks_file}")
        self.logger.info("=" * 80 + "\n")

    def run_first_training(self, save_checkpoint: bool = True):
        """
        Execute the first training run for all strategies.

        This method should be called after creating a new ManagedOnlineManager
        to train the initial models for all enabled strategies.

        Parameters
        ----------
        save_checkpoint : bool, default True
            Whether to save the manager checkpoint after training completes.

        Example
        -------
        >>> manager = ManagedOnlineManager("config/online_config.yaml")
        >>> manager.run_first_training()
        """
        self.logger.info("=" * 80)
        self.logger.info("STARTING FIRST TRAINING")
        self.logger.info("=" * 80)

        try:
            # Run first training on the underlying OnlineManager
            self.logger.info("Executing first_train() on OnlineManager...")
            self.manager.first_train()

            self.logger.info("First training completed successfully")

            # Save checkpoint after training
            if save_checkpoint:
                self._save_checkpoint()
                self.logger.info("Manager checkpoint saved after first training")

            self.logger.info("=" * 80)
            self.logger.info("FIRST TRAINING COMPLETED")
            self.logger.info("=" * 80)

        except Exception as e:
            self.logger.error(f"First training failed: {e}", exc_info=True)
            raise

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

            # Remove duplicate indices (ensemble may create duplicates)
            if len(signals) > 0 and signals.index.duplicated().any():
                dup_count = signals.index.duplicated().sum()
                self.logger.info(f"Removing {dup_count} duplicate indices from signals")
                signals = signals[~signals.index.duplicated(keep='first')]

            self.logger.info(f"Generated {len(signals)} signals")
            self.logger.info(f"Signal date range: {signals.index.get_level_values('datetime').min()} "
                           f"to {signals.index.get_level_values('datetime').max()}")
        except Exception as e:
            self.logger.error(f"Failed to prepare signals: {e}", exc_info=True)
            raise

        # Update manager's signals with deduped version
        # This ensures the manager stores clean signals without duplicates
        if hasattr(self.manager, 'signals'):
            self.manager.signals = signals

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
                                                          'data/checkpoints/online_manager.pkl')
        self.manager.to_pickle(manager_path)
        self.logger.info(f"Checkpoint saved to {manager_path}")

    def _get_all_historical_predictions(self) -> Union[pd.Series, pd.DataFrame]:
        """
        Get all historical predictions from all model recorders.

        This method collects predictions from all trained models across all strategies,
        applies the configured ensemble method, and returns complete historical signals.

        Returns:
            DataFrame or Series with all historical predictions
        """
        self.logger.info("Collecting all historical predictions from recorders...")

        all_predictions = {}  # {strategy_name: [pred1, pred2, ...]}

        # Collect predictions from all strategies
        for strategy in self.manager.strategies:
            strat_name = strategy.name_id
            self.logger.info(f"Processing strategy: {strat_name}")

            # Get all online models (recorders) for this strategy
            online_models = strategy.tool.online_models()

            if not online_models:
                self.logger.warning(f"No online models found for strategy {strat_name}")
                continue

            self.logger.info(f"Found {len(online_models)} online models for {strat_name}")

            strategy_preds = []

            for model_rec in online_models:
                try:
                    # Load predictions from recorder
                    pred = model_rec.load_object("pred.pkl")

                    if pred is not None and len(pred) > 0:
                        strategy_preds.append(pred)
                        self.logger.info(f"  Loaded predictions: {len(pred)} records, "
                                       f"date range: {pred.index.min()} to {pred.index.max()}")
                except Exception as e:
                    self.logger.warning(f"  Failed to load predictions from recorder: {e}")
                    continue

            if strategy_preds:
                all_predictions[strat_name] = strategy_preds

        if not all_predictions:
            self.logger.warning("No predictions found from any strategy")
            return pd.Series()

        # Apply ensemble method
        ensemble_method = self._get_ensemble_method()

        self.logger.info(f"Applying ensemble method: {type(ensemble_method).__name__}")

        try:
            # Build ensemble dict with each model as separate entry
            # qlib ensemble expects: {(strat_name, model_type, model_id): predictions, ...}
            ensemble_dict = {}
            model_counter = 0

            for strat_name, preds in all_predictions.items():
                if len(preds) == 0:
                    continue

                # For rolling strategy, each model should be ensembled separately
                for i, pred_series in enumerate(preds):
                    # Create unique key for each model
                    # Format: (strategy_name, model_class, model_index)
                    model_key = (strat_name, 'LGBModel', f'model_{model_counter}')
                    ensemble_dict[model_key] = pred_series
                    model_counter += 1

                    self.logger.debug(f"  Model {i} of {strat_name}: {len(pred_series)} records")

            # Apply ensemble method
            if len(ensemble_dict) == 0:
                self.logger.warning("No valid strategy signals to ensemble")
                return pd.Series()

            self.logger.info(f"Ensembling {len(ensemble_dict)} models")

            # Use the ensemble callable
            # qlib ensemble methods expect a dict, not a list
            combined_signals = ensemble_method(ensemble_dict)

            # Remove duplicate indices (ensemble may create duplicates)
            # Keep first occurrence
            if len(combined_signals) > 0 and combined_signals.index.duplicated().any():
                dup_count = combined_signals.index.duplicated().sum()
                self.logger.info(f"Removing {dup_count} duplicate indices from ensemble result")
                combined_signals = combined_signals[~combined_signals.index.duplicated(keep='first')]

            self.logger.info(f"Combined signals: {len(combined_signals)} total records")

            # Log date range
            if isinstance(combined_signals.index, pd.MultiIndex):
                dates = combined_signals.index.get_level_values('datetime').unique()
                self.logger.info(f"Date range: {dates.min()} to {dates.max()}")
                self.logger.info(f"Total dates: {len(dates)}")
            else:
                dates = combined_signals.index.unique()
                self.logger.info(f"Date range: {dates.min()} to {dates.max()}")
                self.logger.info(f"Total dates: {len(dates)}")

            return combined_signals

        except Exception as e:
            self.logger.error(f"Failed to apply ensemble: {e}", exc_info=True)

            # Fallback: just concatenate all predictions
            self.logger.info("Using simple fallback: concatenating all predictions")

            all_preds = []
            for strat_name, preds in all_predictions.items():
                all_preds.extend(preds)

            if all_preds:
                combined = pd.concat(all_preds)
                # Remove duplicates, keep last
                combined = combined[~combined.index.duplicated(keep='last')]
                combined = combined.sort_index()
                return combined

            return pd.Series()

    def _export_signals(self, signals: Union[pd.Series, pd.DataFrame]):
        """
        Export signals to file.

        Exports:
        1. Daily snapshot: signals_YYYYMMDD.csv (incremental)
        2. Latest snapshot: signals_latest.csv (most recent)
        3. Historical snapshot: signals_history.csv (all historical predictions)
        """
        export_config = self.config['online_manager'].get('signal_export', {})

        if not export_config.get('enabled', True):
            return

        # Export directory
        export_dir = Path(export_config.get('dir', 'data/signals'))
        export_dir.mkdir(parents=True, exist_ok=True)

        # Export format
        export_format = export_config.get('format', 'csv')

        # Get latest date for filename
        if isinstance(signals, pd.DataFrame):
            latest_date = signals.index.get_level_values('datetime').max()
        else:
            latest_date = signals.index.get_level_values('datetime').max()

        date_str = latest_date.strftime('%Y%m%d')

        # 1. Export daily snapshot (incremental)
        if export_format == 'csv':
            output_path = export_dir / f"signals_{date_str}.csv"
            signals.to_csv(output_path)
            self.logger.info(f"Daily signals exported to {output_path}")

        elif export_format == 'parquet':
            output_path = export_dir / f"signals_{date_str}.parquet"
            signals.to_parquet(output_path)
            self.logger.info(f"Daily signals exported to {output_path}")

        # 2. Export latest signals
        if export_config.get('export_latest', True):
            latest_path = export_dir / "signals_latest.csv"
            signals.to_csv(latest_path)
            self.logger.info(f"Latest signals exported to {latest_path}")

        # 3. Export all historical signals (accumulate all predictions)
        if export_config.get('export_history', True):
            self._export_historical_signals(signals, export_dir, export_format)

    def _export_historical_signals(
        self,
        signals: Union[pd.Series, pd.DataFrame],
        export_dir: Path,
        export_format: str
    ):
        """
        Export all historical signals by collecting from all model recorders.

        This method retrieves ALL historical predictions from all trained models,
        applies the ensemble method, and exports the complete historical record.

        Args:
            signals: Current signals (not used for history export anymore)
            export_dir: Directory to save the file
            export_format: Export format ('csv' or 'parquet')
        """
        history_path = export_dir / f"signals_history.{export_format}"

        try:
            # Get ALL historical predictions from recorders
            self.logger.info("=" * 80)
            self.logger.info("EXPORTING COMPLETE HISTORICAL PREDICTIONS")
            self.logger.info("=" * 80)

            historical_signals = self._get_all_historical_predictions()

            if historical_signals is None or len(historical_signals) == 0:
                self.logger.warning("No historical signals found to export")
                return

            # Export complete historical signals
            if export_format == 'csv':
                historical_signals.to_csv(history_path)
            else:  # parquet
                historical_signals.to_parquet(history_path)

            # Log summary
            if isinstance(historical_signals.index, pd.MultiIndex):
                date_count = len(historical_signals.index.get_level_values('datetime').unique())
                total_count = len(historical_signals)
                date_range = f"{historical_signals.index.get_level_values('datetime').min()} to {historical_signals.index.get_level_values('datetime').max()}"
            else:
                date_count = len(historical_signals.index.unique())
                total_count = len(historical_signals)
                date_range = f"{historical_signals.index.min()} to {historical_signals.index.max()}"

            self.logger.info(f"Historical signals exported to {history_path}")
            self.logger.info(f"  Total dates: {date_count}")
            self.logger.info(f"  Total predictions: {total_count}")
            self.logger.info(f"  Date range: {date_range}")
            self.logger.info("=" * 80)

        except Exception as e:
            self.logger.error(f"Failed to export historical signals: {e}", exc_info=True)
            # Fallback: just export current signals
            try:
                if export_format == 'csv':
                    signals.to_csv(history_path)
                else:
                    signals.to_parquet(history_path)
                self.logger.warning(f"Exported current signals only to {history_path}")
            except Exception as e2:
                self.logger.error(f"Failed to export signals to history file: {e2}")

    def get_signals(self) -> Union[pd.Series, pd.DataFrame]:
        """Get current signals."""
        return self.manager.get_signals()

    def get_online_models(self):
        """Get all online models across all strategies."""
        models = {}
        for strategy in self.manager.strategies:
            models[strategy.name_id] = strategy.tool.online_models()
        return models

    def print_online_models(self):
        """Print detailed information about all online models."""
        print("\n" + "=" * 80)
        print("ONLINE MODELS STATUS")
        print("=" * 80)

        total_models = 0
        for strategy in self.manager.strategies:
            online_models = strategy.tool.online_models()
            model_count = len(online_models)
            total_models += model_count

            print(f"\nStrategy: {strategy.name_id}")
            print(f"  Online Models: {model_count}")

            if model_count > 0:
                for i, model_rec in enumerate(online_models):
                    rec_id = model_rec.info['id']
                    try:
                        task = model_rec.load_object("task")
                        model_class = task["model"]["class"]
                        test_segment = task["dataset"]["kwargs"]["segments"]["test"]
                        print(f"    [{i}] {model_class}")
                        print(f"        Recorder ID: {rec_id[:8]}...")
                        print(f"        Test Segment: {test_segment}")
                    except Exception as e:
                        print(f"    [{i}] Error loading info: {e}")

        print(f"\n{'=' * 80}")
        print(f"Total Online Models: {total_models}")
        print(f"Total Strategies: {len(self.manager.strategies)}")
        print("=" * 80 + "\n")

        return total_models

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
