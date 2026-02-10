# Copyright (c) 2024
# Licensed under the MIT License.

"""
MLflow Integration for Qlib Online Manager

提供完整的 MLflow 集成功能：
- 模型训练指标记录
- 回测结果分析
- 收益曲线可视化
- 自动上传图表和artifacts
"""

import os
import mlflow
import mlflow.sklearn
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List, Optional, Union
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# 设置中文字体支持
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


class MLflowLogger:
    """
    MLflow 日志记录器

    在模型训练和回测过程中记录指标和artifacts
    """

    def __init__(self, experiment_name: str = "qlib_online",
                 tracking_uri: Optional[str] = None,
                 auto_start: bool = True):
        """
        Args:
            experiment_name: MLflow 实验名称
            tracking_uri: MLflow 服务器地址，None 使用默认
            auto_start: 是否自动开始 run
        """
        self.experiment_name = experiment_name
        self.tracking_uri = tracking_uri
        self.active_run = None
        self.run_id = None

        # 设置 tracking URI
        if tracking_uri:
            mlflow.set_tracking_uri(tracking_uri)

        # 设置或创建实验
        self._setup_experiment()

        # 自动开始 run
        if auto_start:
            self.start_run()

    def _setup_experiment(self):
        """设置或创建实验"""
        try:
            # 尝试获取实验
            experiment = mlflow.get_experiment_by_name(self.experiment_name)
            if experiment is None:
                # 创建新实验
                mlflow.create_experiment(self.experiment_name)
                print(f"Created MLflow experiment: {self.experiment_name}")
            else:
                print(f"Using MLflow experiment: {self.experiment_name}")
        except Exception as e:
            print(f"Warning: Failed to setup MLflow experiment: {e}")

    def start_run(self, run_name: Optional[str] = None):
        """开始一个新的 MLflow run"""
        if self.active_run is not None:
            print("Warning: A run is already active. Ending it before starting a new one.")
            self.end_run()

        self.active_run = mlflow.start_run(run_name=run_name)
        self.run_id = self.active_run.info.run_id
        print(f"Started MLflow run: {self.run_id}")
        return self.active_run

    def end_run(self, status: str = "FINISHED"):
        """结束当前的 MLflow run"""
        if self.active_run:
            mlflow.end_run(status=status)
            print(f"Ended MLflow run: {self.run_id}")
            self.active_run = None
            self.run_id = None

    def log_metrics(self, metrics: Dict[str, float], step: Optional[int] = None):
        """
        记录指标到 MLflow

        Args:
            metrics: 指标字典 {metric_name: value}
            step: 训练步数（可选）
        """
        mlflow.log_metrics(metrics, step=step)

    def log_params(self, params: Dict[str, str]):
        """
        记录参数到 MLflow

        Args:
            params: 参数字典 {param_name: value}
        """
        mlflow.log_params(params)

    def log_model(self, model, artifact_path: str):
        """
        记录模型到 MLflow

        Args:
            model: 模型对象
            artifact_path: artifact 路径
        """
        mlflow.sklearn.log_model(model, artifact_path)

    def log_artifact(self, local_path: str, artifact_path: Optional[str] = None):
        """
        记录 artifact（文件）到 MLflow

        Args:
            local_path: 本地文件路径
            artifact_path: MLflow artifact 路径
        """
        mlflow.log_artifact(local_path, artifact_path=artifact_path)

    def log_figure(self, fig: plt.Figure, artifact_file: str):
        """
        记录图表到 MLflow

        Args:
            fig: matplotlib Figure 对象
            artifact_file: 保存的文件名
        """
        temp_path = f"/tmp/{artifact_file}"
        fig.savefig(temp_path, dpi=150, bbox_inches='tight')
        self.log_artifact(temp_path, artifact_file)
        os.remove(temp_path)


class QlibMetricsLogger:
    """
    Qlib 指标记录器

    专门用于记录 Qlib 模型训练和回测的指标
    """

    def __init__(self, mlflow_logger: MLflowLogger):
        """
        Args:
            mlflow_logger: MLflowLogger 实例
        """
        self.logger = mlflow_logger

    def log_training_metrics(self, model, train_result: Dict, step: int = None):
        """
        记录训练指标

        Args:
            model: 训练的模型
            train_result: 训练结果字典
            step: 训练步数
        """
        metrics = {}

        # 训练损失
        if 'train_loss' in train_result:
            metrics['train_loss'] = train_result['train_loss']

        # 验证损失
        if 'valid_loss' in train_result:
            metrics['valid_loss'] = train_result['valid_loss']

        # 训练时间
        if 'train_time' in train_result:
            metrics['train_time_seconds'] = train_result['train_time']

        # 模型复杂度
        if hasattr(model, 'feature_importances_'):
            metrics['n_features'] = len(model.feature_importances_)

        if hasattr(model, 'n_estimators'):
            metrics['n_estimators'] = model.n_estimators

        if hasattr(model, 'num_leaves'):
            metrics['num_leaves'] = model.num_leaves

        self.logger.log_metrics(metrics, step=step)

    def log_prediction_metrics(self, pred: pd.Series, label: pd.Series, prefix: str = ""):
        """
        记录预测指标（IC, Rank IC, etc.）

        Args:
            pred: 预测值
            label: 真实标签
            prefix: 指标前缀
        """
        # 对齐索引
        common_index = pred.index.intersection(label.index)
        pred_aligned = pred.loc[common_index]
        label_aligned = label.loc[common_index]

        if len(common_index) == 0:
            print("Warning: No common index between pred and label")
            return

        # 计算 IC
        ic = pred_aligned.corr(label_aligned)

        # 计算 Rank IC
        rank_ic = pred_aligned.rank().corr(label_aligned.rank())

        metrics = {
            f'{prefix}ic': ic if not np.isnan(ic) else 0,
            f'{prefix}rank_ic': rank_ic if not np.isnan(rank_ic) else 0,
            f'{prefix}n_predictions': len(pred_aligned),
        }

        # 计算 IC 分布
        if len(pred_aligned) > 1:
            metrics[f'{prefix}ic_std'] = pred_aligned.std()

        self.logger.log_metrics(metrics)

    def log_feature_importance(self, model, feature_names: List[str], top_n: int = 20):
        """
        记录并可视化特征重要性

        Args:
            model: 训练好的模型
            feature_names: 特征名称列表
            top_n: 显示前 N 个重要特征
        """
        if not hasattr(model, 'feature_importances_'):
            print("Model does not have feature_importances_ attribute")
            return

        importances = model.feature_importances_
        indices = np.argsort(importances)[::-1][:top_n]

        # 创建 DataFrame
        importance_df = pd.DataFrame({
            'feature': [feature_names[i] for i in indices],
            'importance': importances[indices]
        })

        # 记录为 artifact
        temp_path = '/tmp/feature_importance.csv'
        importance_df.to_csv(temp_path, index=False)
        self.logger.log_artifact(temp_path, 'feature_importance.csv')

        # 可视化
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.barh(range(len(importance_df)), importance_df['importance'].values)
        ax.set_yticks(range(len(importance_df)))
        ax.set_yticklabels(importance_df['feature'].values)
        ax.invert_yaxis()
        ax.set_xlabel('Importance')
        ax.set_title(f'Top {top_n} Feature Importances')
        plt.tight_layout()

        self.logger.log_figure(fig, 'feature_importance.png')
        plt.close()

    def log_model_params(self, model_config: Dict):
        """
        记录模型参数

        Args:
            model_config: 模型配置字典
        """
        params = {}

        # 模型类型
        if 'class' in model_config:
            params['model_class'] = model_config['class']

        # 模型参数
        if 'kwargs' in model_config:
            for key, value in model_config['kwargs'].items():
                params[f'model_{key}'] = str(value)

        self.logger.log_params(params)


class QlibBacktestAnalyzer:
    """
    Qlib 回测分析器

    分析回测结果，计算收益指标，生成可视化图表
    """

    def __init__(self, mlflow_logger: MLflowLogger):
        """
        Args:
            mlflow_logger: MLflowLogger 实例
        """
        self.logger = mlflow_logger

    def analyze_and_log(self, predictions: pd.DataFrame,
                       returns: pd.DataFrame,
                       benchmark_returns: Optional[pd.DataFrame] = None,
                       top_n: int = 50,
                       rebalance_freq: str = 'daily'):
        """
        分析回测结果并记录到 MLflow

        Args:
            predictions: 预测值 DataFrame (datetime, instrument) -> score
            returns: 真实收益率 DataFrame
            benchmark_returns: 基准收益率（可选）
            top_n: 选择 Top N 股票
            rebalance_freq: 再平衡频率 (daily, weekly, monthly)
        """
        print("Analyzing backtest results...")

        # 1. 计算组合收益
        portfolio_returns = self._calculate_portfolio_returns(
            predictions, returns, top_n=top_n
        )

        # 2. 计算收益指标
        metrics = self._calculate_performance_metrics(
            portfolio_returns, benchmark_returns
        )

        # 3. 记录指标
        self.logger.log_metrics(metrics)

        # 4. 生成并记录可视化图表
        self._plot_and_log_returns(
            portfolio_returns, benchmark_returns
        )

        # 5. 生成并记录收益分布图
        self._plot_and_log_distribution(portfolio_returns)

        # 6. 记录收益数据
        self._log_returns_data(portfolio_returns, benchmark_returns)

        print(f"Backtest analysis completed. Metrics: {metrics}")

        return metrics

    def _calculate_portfolio_returns(self, predictions: pd.DataFrame,
                                    returns: pd.DataFrame,
                                    top_n: int = 50) -> pd.Series:
        """
        计算组合收益

        策略：每日选择 Top N 股票，等权重持有
        """
        portfolio_returns_list = []

        # 按日期分组
        for date, pred_group in predictions.groupby(level=0):
            # 选择 Top N
            top_stocks = pred_group.nlargest(top_n).index.get_level_values(1)

            # 获取这些股票的收益
            stock_returns = returns.loc[(date, top_stocks)]

            # 等权重平均
            portfolio_return = stock_returns.mean()
            portfolio_returns_list.append(portfolio_return)

        return pd.Series(portfolio_returns_list, index=predictions.index.get_level_values(0).unique())

    def _calculate_performance_metrics(self, portfolio_returns: pd.Series,
                                      benchmark_returns: Optional[pd.Series] = None) -> Dict:
        """
        计算性能指标
        """
        metrics = {}

        # 累计收益
        metrics['total_return'] = float((1 + portfolio_returns).prod() - 1)

        # 年化收益
        n_days = len(portfolio_returns)
        n_years = n_days / 252  # 假设252个交易日
        metrics['annual_return'] = float((1 + portfolio_returns).prod() ** (1/n_years) - 1)

        # 波动率
        metrics['volatility'] = float(portfolio_returns.std() * np.sqrt(252))

        # 夏普比率（假设无风险利率为0）
        if metrics['volatility'] > 0:
            metrics['sharpe_ratio'] = float(metrics['annual_return'] / metrics['volatility'])
        else:
            metrics['sharpe_ratio'] = 0.0

        # 最大回撤
        cumulative_returns = (1 + portfolio_returns).cumprod()
        running_max = cumulative_returns.expanding().max()
        drawdown = (cumulative_returns - running_max) / running_max
        metrics['max_drawdown'] = float(drawdown.min())

        # 胜率
        metrics['win_rate'] = float((portfolio_returns > 0).sum() / len(portfolio_returns))

        # 与基准对比
        if benchmark_returns is not None and len(benchmark_returns) > 0:
            # 对齐日期
            common_index = portfolio_returns.index.intersection(benchmark_returns.index)
            if len(common_index) > 0:
                port_aligned = portfolio_returns.loc[common_index]
                bench_aligned = benchmark_returns.loc[common_index]

                # 超额收益
                excess_returns = port_aligned - bench_aligned
                metrics['excess_return'] = float(excess_returns.sum())

                # 信息比率
                if excess_returns.std() > 0:
                    metrics['information_ratio'] = float(
                        excess_returns.mean() / excess_returns.std() * np.sqrt(252)
                    )
                else:
                    metrics['information_ratio'] = 0.0

                # 相关系数
                metrics['correlation_with_benchmark'] = float(
                    port_aligned.corr(bench_aligned)
                )

        # 交易次数
        metrics['n_trades'] = n_days

        # 平均持仓时间（假设每日调仓）
        metrics['avg_holding_period'] = 1.0

        return metrics

    def _plot_and_log_returns(self, portfolio_returns: pd.Series,
                             benchmark_returns: Optional[pd.Series] = None):
        """绘制收益曲线并记录"""
        fig, ax = plt.subplots(figsize=(12, 6))

        # 计算累计收益
        cumulative_returns = (1 + portfolio_returns).cumprod()
        ax.plot(cumulative_returns.index, cumulative_returns.values,
                label='Portfolio', linewidth=2)

        # 基准
        if benchmark_returns is not None and len(benchmark_returns) > 0:
            common_index = portfolio_returns.index.intersection(benchmark_returns.index)
            if len(common_index) > 0:
                bench_aligned = benchmark_returns.loc[common_index]
                cumulative_benchmark = (1 + bench_aligned).cumprod()
                ax.plot(cumulative_benchmark.index, cumulative_benchmark.values,
                        label='Benchmark', linewidth=2, alpha=0.7)

        ax.set_xlabel('Date')
        ax.set_ylabel('Cumulative Returns')
        ax.set_title('Portfolio Performance')
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.tight_layout()

        self.logger.log_figure(fig, 'portfolio_returns.png')
        plt.close()

    def _plot_and_log_distribution(self, portfolio_returns: pd.Series):
        """绘制收益分布并记录"""
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))

        # 收益分布直方图
        axes[0].hist(portfolio_returns, bins=50, alpha=0.7, edgecolor='black')
        axes[0].axvline(portfolio_returns.mean(), color='red',
                       linestyle='--', label=f'Mean: {portfolio_returns.mean():.4f}')
        axes[0].set_xlabel('Daily Returns')
        axes[0].set_ylabel('Frequency')
        axes[0].set_title('Distribution of Daily Returns')
        axes[0].legend()
        axes[0].grid(True, alpha=0.3)

        # Q-Q 图
        from scipy import stats
        stats.probplot(portfolio_returns, dist="norm", plot=axes[1])
        axes[1].set_title('Q-Q Plot')
        axes[1].grid(True, alpha=0.3)

        plt.tight_layout()

        self.logger.log_figure(fig, 'returns_distribution.png')
        plt.close()

    def _log_returns_data(self, portfolio_returns: pd.Series,
                          benchmark_returns: Optional[pd.Series] = None):
        """记录收益数据为 CSV artifact"""
        # 组合收益
        df = pd.DataFrame({'portfolio_returns': portfolio_returns})

        # 基准收益
        if benchmark_returns is not None:
            common_index = portfolio_returns.index.intersection(benchmark_returns.index)
            if len(common_index) > 0:
                df['benchmark_returns'] = benchmark_returns.loc[common_index]
                df['excess_returns'] = df['portfolio_returns'] - df['benchmark_returns']

        temp_path = '/tmp/returns_data.csv'
        df.to_csv(temp_path)
        self.logger.log_artifact(temp_path, 'returns_data.csv')
        os.remove(temp_path)


class MLflowEnabledStrategy:
    """
    MLflow 集成策略包装器

    包装任何 OnlineStrategy，自动记录训练和回测指标到 MLflow
    """

    def __init__(self, strategy, mlflow_logger: MLflowLogger):
        """
        Args:
            strategy: 原始的 OnlineStrategy 实例
            mlflow_logger: MLflowLogger 实例
        """
        self.strategy = strategy
        self.mlflow_logger = mlflow_logger
        self.metrics_logger = QlibMetricsLogger(mlflow_logger)
        self.backtest_analyzer = QlibBacktestAnalyzer(mlflow_logger)

        # 代理策略的所有属性和方法
        self.name_id = strategy.name_id
        self.tool = strategy.tool

    def first_tasks(self):
        """代理 first_tasks"""
        return self.strategy.first_tasks()

    def prepare_tasks(self, cur_time, **kwargs):
        """代理 prepare_tasks"""
        tasks = self.strategy.prepare_tasks(cur_time, **kwargs)

        # 记录任务信息
        if tasks:
            self.mlflow_logger.log_params({
                f'strategy_{self.name_id}_n_tasks': str(len(tasks)),
                f'strategy_{self.name_id}_cur_time': str(cur_time),
            })

        return tasks

    def prepare_online_models(self, trained_models, cur_time=None):
        """代理 prepare_online_models，添加指标记录"""
        # 记录模型指标
        for i, model_recorder in enumerate(trained_models):
            try:
                # 加载模型
                model = model_recorder.load_object('params.pkl')

                # 记录模型参数
                task = model_recorder.load_object('task')
                if 'model' in task:
                    self.metrics_logger.log_model_params(task['model'])

                # 加载预测和标签
                pred = model_recorder.load_object('pred.pkl')

                # 如果有标签，计算 IC
                try:
                    label = model_recorder.load_object('label.pkl')
                    self.metrics_logger.log_prediction_metrics(
                        pred.iloc[:, 0] if isinstance(pred, pd.DataFrame) else pred,
                        label.iloc[:, 0] if isinstance(label, pd.DataFrame) else label,
                        prefix=f'model_{i}_'
                    )
                except:
                    print(f"Warning: No label found for model {i}")

                # 特征重要性
                if hasattr(model, 'feature_importances_'):
                    # 获取特征名称
                    handler = model_recorder.load_object('dataset')
                    if hasattr(handler, 'get_cols()'):
                        feature_names = handler.get_cols()
                    else:
                        feature_names = [f'feature_{i}' for i in range(len(model.feature_importances_))]

                    self.metrics_logger.log_feature_importance(model, feature_names)

            except Exception as e:
                print(f"Warning: Failed to log metrics for model {i}: {e}")

        # 调用原始方法
        return self.strategy.prepare_online_models(trained_models, cur_time)

    def get_collector(self, **kwargs):
        """代理 get_collector"""
        return self.strategy.get_collector(**kwargs)

    def run_backtest_and_log(self, start_date: str, end_date: str,
                             benchmark_data: Optional[pd.DataFrame] = None):
        """
        运行回测并记录结果

        Args:
            start_date: 回测开始日期
            end_date: 回测结束日期
            benchmark_data: 基准数据
        """
        print(f"Running backtest for {self.name_id} from {start_date} to {end_date}")

        # 获取预测
        collector = self.strategy.get_collector()
        predictions = collector()

        # 提取预测
        pred_key = None
        for key in predictions.keys():
            if 'pred' in key:
                pred_key = key
                break

        if pred_key is None:
            print("No predictions found for backtest")
            return

        pred_df = predictions[pred_key]

        # 加载收益率数据
        from qlib.data import D
        returns = D.features(
            instruments=pred_df.index.get_level_values('1').unique(),
            fields=["$return"],  # 使用 Qlib 的收益率字段
            start_time=start_date,
            end_time=end_date
        )

        if returns is None or len(returns) == 0:
            print("Warning: No returns data available for backtest")
            return

        # 运行回测分析
        self.backtest_analyzer.analyze_and_log(
            predictions=pred_df,
            returns=returns,
            benchmark_returns=benchmark_data
        )
