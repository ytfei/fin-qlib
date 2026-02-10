# Copyright (c) 2024
# Licensed under the MIT License.

"""
Advanced ensemble methods for combining multiple strategy signals.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Union, Callable
from qlib.model.ens.ensemble import Ensemble
from qlib.workflow.online.strategy import RollingStrategy
from qlib.workflow.online.manager import OnlineManager
from qlib.data import D


# Import AverageEnsemble from qlib
try:
    from qlib.model.ens.ensemble import AverageEnsemble as _AverageEnsemble
    AverageEnsemble = _AverageEnsemble
except ImportError:
    # Fallback implementation
    class AverageEnsemble(Ensemble):
        def __call__(self, ensemble_dict: dict) -> pd.DataFrame:
            values = list(ensemble_dict.values())
            if len(values) == 1:
                return values[0]
            return pd.concat(values, axis=1).mean(axis=1)


class WeightedEnsemble(Ensemble):
    """
    Weighted average ensemble for multiple strategy predictions.

    Example:
        manager.prepare_signals(
            prepare_func=WeightedEnsemble({
                'LGB_strategy': 0.5,
                'XGB_strategy': 0.3,
                'MLP_strategy': 0.2
            })
        )
    """

    def __init__(self, weights: Dict[str, float]):
        """
        Args:
            weights: Strategy name -> weight mapping. Weights should sum to 1.0.
        """
        total = sum(weights.values())
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Weights should sum to 1.0, got {total}")
        self.weights = weights

    def __call__(self, ensemble_dict: dict) -> pd.DataFrame:
        """
        Combine predictions using weighted average.

        Args:
            ensemble_dict: {(strategy_name, artifact_name): prediction_df}

        Returns:
            Combined predictions DataFrame
        """
        weighted_pred = None

        for key, pred in ensemble_dict.items():
            strategy_name = key[0]
            weight = self.weights.get(strategy_name, 0.0)

            if weight == 0.0:
                continue

            # Ensure pred is DataFrame
            if isinstance(pred, pd.Series):
                pred = pred.to_frame('score')

            if weighted_pred is None:
                weighted_pred = pred * weight
            else:
                weighted_pred += pred * weight

        return weighted_pred


class BestModelEnsemble(Ensemble):
    """
    Select the best single model based on historical performance.

    Example:
        manager.prepare_signals(
            prepare_func=BestModelEnsemble(best_strategy='LGB_strategy')
        )
    """

    def __init__(self, best_strategy: str = None, metric: str = 'ic'):
        """
        Args:
            best_strategy: If specified, always use this strategy.
            metric: Metric to use for auto-selection ('ic', 'rank_ic', 'sharpe').
        """
        self.best_strategy = best_strategy
        self.metric = metric

    def __call__(self, ensemble_dict: dict) -> pd.DataFrame:
        """
        Select and return predictions from the best strategy.
        """
        if self.best_strategy is not None:
            # Use specified strategy
            for key, pred in ensemble_dict.items():
                if key[0] == self.best_strategy:
                    return pred
            raise ValueError(f"Strategy '{self.best_strategy}' not found in ensemble_dict")

        # Auto-select based on metric
        best_key = self._find_best_strategy(ensemble_dict)
        return ensemble_dict[best_key]

    def _find_best_strategy(self, ensemble_dict: dict) -> tuple:
        """
        Find the best performing strategy based on historical metrics.
        """
        strategy_scores = {}

        for key in ensemble_dict.keys():
            strategy_name = key[0]
            score = self._get_strategy_metric(strategy_name, self.metric)
            strategy_scores[strategy_name] = score

        best_strategy = max(strategy_scores.items(), key=lambda x: x[1])[0]

        # Find the corresponding key
        for key in ensemble_dict.keys():
            if key[0] == best_strategy:
                return key

        raise ValueError(f"Could not find key for strategy '{best_strategy}'")

    def _get_strategy_metric(self, strategy_name: str, metric: str) -> float:
        """
        Retrieve historical metric for a strategy.

        NOTE: This is a simplified implementation. In production,
        you should cache these metrics or store them in a database.
        """
        # TODO: Implement metric retrieval from Recorder or cache
        # For now, return a default value
        return 0.0


class DynamicWeightEnsemble(Ensemble):
    """
    Dynamically adjust weights based on recent performance.

    Uses softmax transformation on recent metrics to compute weights.

    Example:
        manager.prepare_signals(
            prepare_func=DynamicWeightEnsemble(lookback_days=30, metric='ic')
        )
    """

    def __init__(self, lookback_days: int = 30, metric: str = 'ic'):
        """
        Args:
            lookback_days: Number of days to look back for performance calculation.
            metric: Metric to use ('ic', 'rank_ic').
        """
        self.lookback = lookback_days
        self.metric = metric
        self._metric_cache = {}  # Cache for strategy metrics

    def __call__(self, ensemble_dict: dict) -> pd.DataFrame:
        """
        Combine predictions using dynamic weights based on recent performance.
        """
        # 1. Get recent performance for each strategy
        recent_performances = {}
        for key in ensemble_dict.keys():
            strategy_name = key[0]
            metric_value = self._get_recent_metric(strategy_name, self.lookback)
            recent_performances[strategy_name] = metric_value

        # 2. Convert to weights using softmax
        performances = np.array(list(recent_performances.values()))

        # Handle case where all performances are similar or zero
        if np.std(performances) < 1e-6:
            # Use equal weights
            weights = np.ones(len(performances)) / len(performances)
        else:
            # Softmax transformation
            exp_perfs = np.exp(performances - np.max(performances))  # For numerical stability
            weights = exp_perfs / np.sum(exp_perfs)

        # 3. Weighted average
        result = None
        strategy_names = list(recent_performances.keys())

        for key, pred in ensemble_dict.items():
            strategy_name = key[0]
            if strategy_name not in strategy_names:
                continue

            idx = strategy_names.index(strategy_name)
            weight = weights[idx]

            if isinstance(pred, pd.Series):
                pred = pred.to_frame('score')

            if result is None:
                result = pred * weight
            else:
                result += pred * weight

        return result

    def _get_recent_metric(self, strategy_name: str, lookback_days: int) -> float:
        """
        Get recent metric value for a strategy.

        NOTE: Simplified implementation. Production should:
        1. Cache metrics to avoid repeated calculations
        2. Query from database or persistent storage
        """
        # TODO: Implement proper metric retrieval
        # For now, return a mock value
        return 0.05 + np.random.randn() * 0.01  # Mock IC ~ 5%


class VotingEnsemble(Ensemble):
    """
    Voting-based ensemble: select stocks that appear in top-N of multiple models.

    Example:
        manager.prepare_signals(
            prepare_func=VotingEnsemble(top_n=50, min_votes=2)
        )
    """

    def __init__(self, top_n: int = 50, min_votes: int = None,
                 return_type: str = 'weighted'):
        """
        Args:
            top_n: Number of top stocks to consider from each model.
            min_votes: Minimum number of models that must vote for a stock.
                      If None, requires majority (> half of models).
            return_type: 'weighted' - return weighted average predictions
                        'uniform' - return uniform predictions for selected stocks
        """
        self.top_n = top_n
        self.min_votes = min_votes
        self.return_type = return_type

    def __call__(self, ensemble_dict: dict) -> pd.DataFrame:
        """
        Select stocks through voting and return their predictions.
        """
        from collections import Counter

        # 1. Each model selects top N stocks
        top_stocks_sets = []
        all_predictions = {}

        for key, pred in ensemble_dict.items():
            if isinstance(pred, pd.DataFrame):
                latest_pred = pred.iloc[-1]  # Get most recent prediction
            else:
                latest_pred = pred

            # Get top N stocks
            top_stocks = set(latest_pred.nlargest(self.top_n).index)
            top_stocks_sets.append(top_stocks)

            # Store predictions for later averaging
            strategy_name = key[0]
            all_predictions[strategy_name] = latest_pred

        # 2. Count votes
        votes = Counter()
        for stock_set in top_stocks_sets:
            for stock in stock_set:
                votes[stock] += 1

        # 3. Determine threshold
        threshold = self.min_votes
        if threshold is None:
            threshold = len(top_stocks_sets) // 2

        # 4. Select stocks with sufficient votes
        selected_stocks = {s for s, c in votes.items() if c >= threshold}

        if len(selected_stocks) == 0:
            # Fallback: return top stocks from best model
            return ensemble_dict[list(ensemble_dict.keys())[0]]

        # 5. Return predictions
        if self.return_type == 'uniform':
            # Return uniform scores
            result = pd.Series(1.0, index=list(selected_stocks))
        else:
            # Weighted average of predictions
            result = None
            count = 0

            for strategy_name, pred in all_predictions.items():
                # Filter to selected stocks
                filtered = pred[pred.index.isin(selected_stocks)]

                if result is None:
                    result = filtered
                else:
                    # Reindex to align stocks
                    result = result.add(filtered, fill_value=0)
                count += 1

            result = result / count

        return result.to_frame('score')


class SignalEvaluator:
    """
    Evaluate and compare signals from multiple strategies.

    Provides tools to:
    1. Calculate backtest metrics (IC, Sharpe, etc.)
    2. Compare strategy performance
    3. Recommend ensemble method
    """

    def __init__(self, manager: OnlineManager):
        """
        Args:
            manager: OnlineManager instance with strategies to evaluate.
        """
        self.manager = manager

    def evaluate_all(self, start_date: str, end_date: str) -> Dict[str, Dict[str, float]]:
        """
        Evaluate all strategies over the given date range.

        Returns:
            Dict mapping strategy_name -> {metric_name: metric_value}
        """
        results = {}

        for strategy in self.manager.strategies:
            strategy_name = strategy.name_id

            # Get predictions from this strategy
            try:
                collector = strategy.get_collector()
                predictions = collector()

                # Extract prediction DataFrame
                pred_key = None
                for key in predictions.keys():
                    if 'pred' in key:
                        pred_key = key
                        break

                if pred_key is None:
                    print(f"Warning: No predictions found for {strategy_name}")
                    continue

                pred_df = predictions[pred_key]

                # Calculate metrics
                metrics = self._calculate_metrics(pred_df, start_date, end_date)
                results[strategy_name] = metrics

            except Exception as e:
                print(f"Error evaluating {strategy_name}: {e}")
                results[strategy_name] = {'error': str(e)}

        return results

    def _calculate_metrics(self, pred_df: pd.DataFrame,
                          start_date: str, end_date: str) -> Dict[str, float]:
        """
        Calculate backtest metrics for predictions.

        Returns:
            Dict with metrics: ic, rank_ic, sharpe, etc.
        """
        # Filter by date range
        pred_df = pred_df.loc[
            (pred_df.index.get_level_values('datetime') >= start_date) &
            (pred_df.index.get_level_values('datetime') <= end_date)
        ]

        metrics = {}

        # IC (Information Coefficient)
        # NOTE: This requires label data. Simplified here.
        # In production, you would load actual returns and calculate correlation
        metrics['ic'] = self._mock_ic(pred_df)
        metrics['rank_ic'] = self._mock_rank_ic(pred_df)

        # Sharpe ratio (requires portfolio returns)
        # Simplified implementation
        metrics['sharpe'] = self._mock_sharpe(pred_df)

        # Number of predictions
        metrics['n_predictions'] = len(pred_df)

        return metrics

    def _mock_ic(self, pred_df: pd.DataFrame) -> float:
        """Mock IC calculation. Replace with actual implementation."""
        return 0.05 + np.random.randn() * 0.02

    def _mock_rank_ic(self, pred_df: pd.DataFrame) -> float:
        """Mock Rank IC calculation. Replace with actual implementation."""
        return 0.03 + np.random.randn() * 0.015

    def _mock_sharpe(self, pred_df: pd.DataFrame) -> float:
        """Mock Sharpe calculation. Replace with actual implementation."""
        return 1.5 + np.random.randn() * 0.3

    def recommend_ensemble_method(self, evaluation_results: Dict,
                                 **kwargs) -> Ensemble:
        """
        Recommend ensemble method based on evaluation results.

        Args:
            evaluation_results: Output from evaluate_all()
            **kwargs: Additional parameters for ensemble methods

        Returns:
            Ensemble instance
        """
        # Filter out error results
        valid_results = {k: v for k, v in evaluation_results.items() if 'error' not in v}

        if len(valid_results) == 0:
            raise ValueError("No valid evaluation results")

        if len(valid_results) == 1:
            # Only one strategy, use directly
            only_strategy = list(valid_results.keys())[0]
            return BestModelEnsemble(best_strategy=only_strategy)

        # Compare best and second best
        sorted_strategies = sorted(valid_results.items(),
                                  key=lambda x: x[1].get('ic', 0),
                                  reverse=True)

        best_name, best_metrics = sorted_strategies[0]
        second_name, second_metrics = sorted_strategies[1]

        best_ic = best_metrics.get('ic', 0)
        second_ic = second_metrics.get('ic', 0)

        # Decision logic
        if best_ic > second_ic * 1.3:
            # Best strategy is significantly better
            print(f"Recommendation: Use single best strategy '{best_name}' "
                  f"(IC={best_ic:.4f} >> {second_name} IC={second_ic:.4f})")
            return BestModelEnsemble(best_strategy=best_name)

        elif abs(best_ic - second_ic) < 0.01:
            # Strategies perform similarly, use voting
            print(f"Recommendation: Use voting ensemble "
                  f"(similar performance: {best_name} IC={best_ic:.4f}, "
                  f"{second_name} IC={second_ic:.4f})")
            return VotingEnsemble(top_n=kwargs.get('top_n', 50))

        else:
            # Use dynamic weights
            print(f"Recommendation: Use dynamic weighted ensemble "
                  f"({best_name} IC={best_ic:.4f}, {second_name} IC={second_ic:.4f})")
            return DynamicWeightEnsemble(
                lookback_days=kwargs.get('lookback_days', 30)
            )

    def print_comparison(self, evaluation_results: Dict):
        """
        Print a formatted comparison of strategy performance.
        """
        print("\n" + "=" * 80)
        print("Strategy Performance Comparison")
        print("=" * 80)

        print(f"{'Strategy':<20} {'IC':>10} {'Rank IC':>10} {'Sharpe':>10} {'Status':>15}")
        print("-" * 80)

        for strategy_name, metrics in sorted(evaluation_results.items()):
            if 'error' in metrics:
                print(f"{strategy_name:<20} {'N/A':>10} {'N/A':>10} {'N/A':>10} {'ERROR':>15}")
            else:
                ic = metrics.get('ic', 0)
                rank_ic = metrics.get('rank_ic', 0)
                sharpe = metrics.get('sharpe', 0)
                print(f"{strategy_name:<20} {ic:>10.4f} {rank_ic:>10.4f} {sharpe:>10.2f} {'OK':>15}")

        print("=" * 80)
