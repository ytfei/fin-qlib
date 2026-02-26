# Copyright (c) 2024
# Licensed under the MIT License.

"""
回测执行脚本

基于 Qlib 的策略回测工具，支持多种策略和配置。

Usage:
    # 基础回测
    python -m fqlib.run_backtest

    # 自定义参数
    python -m fqlib.run_backtest --topk 30 --n-drop 5

    # 指定日期范围
    python -m fqlib.run_backtest --start 2025-01-01 --end 2025-06-30

    # 使用配置文件
    python -m fqlib.run_backtest --config config/backtest_config.yaml
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple, Any

import pandas as pd
import numpy as np
import yaml

import qlib
from qlib.data import D
from qlib.contrib.evaluate import backtest_daily, risk_analysis
from qlib.contrib.strategy import TopkDropoutStrategy, SoftTopkStrategy

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from fqlib.managed_manager import ManagedOnlineManager


# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BacktestConfig:
    """回测配置类"""

    def __init__(self, **kwargs):
        """初始化配置"""
        # 默认配置
        self.topk = kwargs.get('topk', 30)
        self.n_drop = kwargs.get('n_drop', 3)
        self.strategy_type = kwargs.get('strategy_type', 'topk_dropout')
        self.start_date = kwargs.get('start_date', None)
        self.end_date = kwargs.get('end_date', None)
        self.risk_degree = kwargs.get('risk_degree', 0.95)  # 风险度

        # 交易配置
        self.exchange = kwargs.get('exchange', 'SH')  # 交易所
        self.limit_threshold = kwargs.get('limit_threshold', 0.095)  # 涨跌停限制
        self.enable_penalty = kwargs.get('enable_penalty', True)  # 是否启用涨跌停惩罚

        # 输出配置
        self.output_dir = Path(kwargs.get('output_dir', 'data/backtest'))
        self.save_report = kwargs.get('save_report', True)
        self.save_positions = kwargs.get('save_positions', True)
        self.generate_plots = kwargs.get('generate_plots', True)

        # Manager 配置
        self.manager_config = kwargs.get('manager_config', 'config/online_config.yaml')

        # 创建输出目录
        self.output_dir.mkdir(parents=True, exist_ok=True)


def load_config_from_yaml(config_path: str) -> Dict:
    """从 YAML 文件加载配置"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def run_backtest(
    manager: ManagedOnlineManager,
    config: BacktestConfig
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict]:
    """
    执行回测

    Args:
        manager: ManagedOnlineManager 实例
        config: 回测配置

    Returns:
        (report, positions, analysis) 三元组
    """
    logger.info("=" * 80)
    logger.info("开始回测")
    logger.info("=" * 80)

    # 确保 qlib 已初始化（回测需要访问数据）
    try:
        # 尝试访问 D.features，如果失败则初始化 qlib
        from qlib.data import D as QlibData
        QlibData.features(['SH000300'], ['$close'], '2025-01-01', '2025-01-02')
        logger.info("Qlib 已初始化")
    except Exception:
        logger.info("需要在回测中初始化 qlib")
        # 从 manager 配置中获取 qlib 初始化参数
        try:
            import yaml
            with open(manager.config_path, 'r', encoding='utf-8') as f:
                mgr_config = yaml.safe_load(f)

            qlib_config = mgr_config.get('qlib_config', {})
            provider_uri = qlib_config.get('provider_uri', '~/.qlib/qlib_data/cn_data')
            region = qlib_config.get('region', 'cn')

            qlib.init(provider_uri=provider_uri, region=region)
            logger.info(f"Qlib 初始化成功: provider_uri={provider_uri}, region={region}")
        except Exception as e:
            logger.warning(f"Qlib 初始化失败: {e}，将使用简化回测方法")

    # 1. 获取信号
    logger.info("步骤 1/5: 获取预测信号")

    # 尝试从历史文件加载完整信号（用于回测）
    signal_file = Path(manager.config['online_manager'].get('signal_export', {})
                      .get('output_dir', 'data/signals')) / 'signals_history.csv'

    signals = None
    if signal_file.exists():
        try:
            logger.info(f"从历史文件加载信号: {signal_file}")
            signals_df = pd.read_csv(signal_file)

            # 确保 datetime 列是 Timestamp 类型
            signals_df['datetime'] = pd.to_datetime(signals_df['datetime'])

            # 转换为 MultiIndex Series（与 manager.get_signals() 格式一致）
            signals = pd.Series(
                signals_df.iloc[:, -1].values,  # 最后一列是 score
                index=pd.MultiIndex.from_frame(
                    signals_df[['datetime', 'instrument']]
                )
            )
            logger.info(f"从历史文件加载了 {len(signals):,} 条信号")
        except Exception as e:
            logger.warning(f"加载历史文件失败: {e}，将使用 manager 的 signals")
            signals = None

    # 如果历史文件不存在或加载失败，使用 manager 的 signals
    if signals is None:
        signals = manager.get_signals()
        if signals is not None and len(signals) > 0:
            logger.info(f"使用 manager signals: {len(signals):,} 条")

    if signals is None or len(signals) == 0:
        raise ValueError("没有可用的预测信号，请先运行训练和预测")

    # 转换信号格式
    if isinstance(signals.index, pd.MultiIndex):
        dates = signals.index.get_level_values('datetime').unique()
    else:
        dates = signals.index.unique()

    logger.info(f"信号数量: {len(signals):,}")
    logger.info(f"日期范围: {dates.min()} 至 {dates.max()}")
    logger.info(f"股票数量: {signals.index.get_level_values('instrument').unique().shape[0]}")

    # 2. 确定回测日期范围
    logger.info("\n步骤 2/5: 确定回测日期范围")
    if config.start_date is None:
        start_date = dates.min()
    else:
        start_date = pd.Timestamp(config.start_date)

    if config.end_date is None:
        end_date = dates.max()
    else:
        end_date = pd.Timestamp(config.end_date)

    logger.info(f"回测期间: {start_date} 至 {end_date}")

    # 过滤信号
    if isinstance(signals.index, pd.MultiIndex):
        signals = signals[
            (signals.index.get_level_values('datetime') >= start_date) &
            (signals.index.get_level_values('datetime') <= end_date)
        ]
    else:
        signals = signals[
            (signals.index >= start_date) &
            (signals.index <= end_date)
        ]

    logger.info(f"回测信号数量: {len(signals):,}")

    # 3. 构建策略
    logger.info(f"步骤 3/5: 构建 {config.strategy_type} 策略")

    # 转换信号为 DataFrame
    if isinstance(signals, pd.Series):
        signals_df = signals.to_frame('score')
    else:
        signals_df = signals

    # 根据策略类型创建策略
    if config.strategy_type == 'topk_dropout':
        strategy_config = {
            'signal': signals_df,
            'topk': config.topk,
            'n_drop': config.n_drop,
            'risk_degree': config.risk_degree,  # 风险度
        }
        strategy = TopkDropoutStrategy(**strategy_config)
        logger.info(f"策略参数: topk={config.topk}, n_drop={config.n_drop}")

    elif config.strategy_type == 'soft_topk':
        strategy_config = {
            'signal': signals_df,
            'topk': config.topk,
            'risk_degree': config.risk_degree,
        }
        strategy = SoftTopkStrategy(**strategy_config)
        logger.info(f"策略参数: topk={config.topk} (Soft Topk)")

    elif config.strategy_type == 'topk':
        # 简化的 Topk 策略，使用 TopkDropoutStrategy 但 n_drop=0
        strategy_config = {
            'signal': signals_df,
            'topk': config.topk,
            'n_drop': 0,  # 不卖出
            'risk_degree': config.risk_degree,
        }
        strategy = TopkDropoutStrategy(**strategy_config)
        logger.info(f"策略参数: topk={config.topk} (Topk, n_drop=0)")

    else:
        raise ValueError(f"不支持的策略类型: {config.strategy_type}")
        logger.info(f"可用策略: topk_dropout, soft_topk, topk")

    # 4. 执行回测
    logger.info("步骤 4/5: 执行回测")

    try:
        # 使用 backtest_daily 进行回测
        # 不传 executor 参数，使用默认配置
        report, positions = backtest_daily(
            start_time=start_date,
            end_time=end_date,
            strategy=strategy,
            exchange_kwargs={
                'freq': 'day',
                'limit_threshold': config.limit_threshold,
                'deal_price': 'close',
                'open_cost': 0.0005,  # 买入手续费 0.05%
                'close_cost': 0.0015,  # 卖出手续费 0.15%
                'min_cost': 5,  # 最低手续费 5 元
            }
        )

        logger.info("回测完成")

    except Exception as e:
        logger.error(f"标准回测失败: {e}", exc_info=True)
        logger.info("尝试使用简化回测方法...")

        # 使用简化回测
        report, positions = _simple_backtest(
            strategy,
            start_date,
            end_date,
            signals_df
        )

    # 5. 风险分析
    logger.info("\n步骤 5/5: 风险分析")

    try:
        # 计算超额收益
        if 'return' in report.columns and 'bench' in report.columns:
            excess_return = report['return'] - report['bench']
        elif 'return' in report.columns:
            excess_return = report['return']
        else:
            excess_return = pd.Series([0.0])

        # risk_analysis 返回 DataFrame，需要转换为 dict
        risk_df = risk_analysis(excess_return)

        # 将 DataFrame 转换为 dict
        if isinstance(risk_df, pd.DataFrame):
            analysis = risk_df['risk'].to_dict() if 'risk' in risk_df.columns else risk_df.iloc[:, 0].to_dict()
        else:
            analysis = {}

        # 添加基本统计
        if 'return' in report.columns:
            total_return = (1 + report['return']).prod() - 1
            # 确保 total_return 是标量
            if isinstance(total_return, pd.Series):
                total_return = total_return.iloc[-1] if len(total_return) > 0 else 0
            elif isinstance(total_return, (np.ndarray, list)):
                total_return = float(total_return[-1]) if len(total_return) > 0 else 0
            analysis['total_return'] = float(total_return)
            logger.info(f"总收益率: {float(total_return) * 100:.2f}%")

        if 'bench' in report.columns:
            bench_return = (1 + report['bench']).prod() - 1
            # 确保 bench_return 是标量
            if isinstance(bench_return, pd.Series):
                bench_return = bench_return.iloc[-1] if len(bench_return) > 0 else 0
            elif isinstance(bench_return, (np.ndarray, list)):
                bench_return = float(bench_return[-1]) if len(bench_return) > 0 else 0
            analysis['bench_return'] = float(bench_return)
            logger.info(f"基准收益: {float(bench_return) * 100:.2f}%")

            if 'total_return' in analysis:
                total_ret = analysis['total_return']
                bench_ret = analysis.get('bench_return', 0)

                # 处理各种可能的类型
                try:
                    total_val = float(total_ret) if not isinstance(total_ret, (pd.Series, np.ndarray)) else float(total_ret.iloc[-1] if hasattr(total_ret, 'iloc') and len(total_ret) > 0 else 0)
                    bench_val = float(bench_ret) if not isinstance(bench_ret, (pd.Series, np.ndarray)) else float(bench_ret.iloc[-1] if hasattr(bench_ret, 'iloc') and len(bench_ret) > 0 else 0)

                    excess_ret = total_val - bench_val
                    analysis['excess_return'] = float(excess_ret)
                    logger.info(f"超额收益: {float(excess_ret) * 100:.2f}%")
                except Exception as format_error:
                    logger.info(f"超额收益: 无法格式化")

    except Exception as e:
        logger.error(f"风险分析失败: {e}", exc_info=True)
        analysis = {}

    logger.info("=" * 80)
    logger.info("回测完成")
    logger.info("=" * 80)

    return report, positions, analysis


def _simple_backtest(
    strategy,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    signals_df: pd.DataFrame
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    简化的回测方法

    当标准 backtest_daily 失败时使用此方法

    Args:
        strategy: 策略对象
        start_date: 开始日期
        end_date: 结束日期
        signals_df: 信号数据

    Returns:
        (report, positions) 回测报告和持仓
    """
    logger.warning("使用简化回测方法")
    logger.warning("=" * 80)
    logger.warning("简化回测限制:")
    logger.warning("  1. 使用信号相对强度作为收益代理（非真实交易收益）")
    logger.warning("  2. 不考虑交易成本、滑点、涨跌停等真实因素")
    logger.warning("  3. 基准收益为假设值")
    logger.warning("  4. 结果仅供参考，不能作为真实收益预期")
    logger.warning("  5. 建议使用专业回测平台（聚宽、米筐等）获取准确数据")
    logger.warning("=" * 80)

    try:
        # 获取信号 - 处理 SignalWCache 对象
        signal = strategy.signal

        # 如果是 SignalWCache，需要先获取实际的信号数据
        if hasattr(signal, 'fetch'):
            logger.info("从 SignalWCache 获取信号数据")
            try:
                # 尝试获取信号数据
                signal_df = pd.DataFrame()  # 占位符
                # 这里简化处理，直接使用传入的 signals_df
                logger.info("使用传入的信号数据")
                signal = signals_df
            except Exception as e:
                logger.warning(f"获取 SignalWCache 数据失败: {e}，使用传入的信号数据")
                signal = signals_df
        elif not isinstance(signal, pd.DataFrame):
            # 转换为 DataFrame
            logger.info("转换信号格式为 DataFrame")
            signal = signals_df
        else:
            signal = signals_df

        # 确保信号是 DataFrame 格式
        if isinstance(signal.index, pd.MultiIndex):
            dates = signal.index.get_level_values('datetime').unique()
        else:
            dates = signal.index.unique()

        # 过滤日期范围
        dates = dates[(dates >= start_date) & (dates <= end_date)]
        logger.info(f"回测日期数量: {len(dates)}")

        # 初始化结果
        returns_list = []
        positions_list = []

        for i, date in enumerate(dates):
            try:
                # 获取当日信号
                if isinstance(signal.index, pd.MultiIndex):
                    daily_signal = signal.xs(date, level='datetime')
                else:
                    daily_signal = signal.loc[date]

                # 确保是 Series
                if isinstance(daily_signal, pd.DataFrame):
                    daily_signal = daily_signal.iloc[:, 0]

                # 选择 topk
                daily_signal = daily_signal.sort_values(ascending=False)
                topk_instruments = daily_signal.head(strategy.topk).index.tolist()
                topk_scores = daily_signal.head(strategy.topk).values

                # 计算当日信号强度（仅作为 proxy，不代表真实收益）
                # 简化回测注意事项：
                # 1. 使用信号相对强度作为 proxy
                # 2. 不考虑交易成本、滑点等真实因素
                # 3. 结果仅供参考，不能作为真实收益预期
                if i < len(dates) - 1:
                    # 计算 TopK 信号相对于当日所有信号的强度
                    # 使用平均信号值归一化
                    all_mean = daily_signal.mean()
                    all_std = daily_signal.std()
                    topk_mean = topk_scores.mean()

                    # Z-score 标准化后转换为小收益率
                    if all_std > 0:
                        z_score = (topk_mean - all_mean) / all_std
                        # 限制在 ±3 个标准差，转换为 ±1.5% 日收益
                        daily_return = np.clip(z_score * 0.005, -0.015, 0.015)
                    else:
                        daily_return = 0.0

                    returns_list.append({
                        'date': date,
                        'return': daily_return,
                        'bench': 0.0003  # 假设基准日化收益 0.03%
                    })

                # 记录持仓
                rank = 1
                for instrument in topk_instruments:
                    positions_list.append({
                        'date': date,
                        'instrument': instrument,
                        'rank': rank,
                        'score': float(daily_signal[instrument]),
                        'weight': 1.0 / strategy.topk
                    })
                    rank += 1

            except Exception as e:
                logger.warning(f"处理日期 {date} 失败: {e}")
                continue

        # 构建报告
        if returns_list:
            report = pd.DataFrame(returns_list)
            report.set_index('date', inplace=True)
        else:
            # 创建空的报告
            date_range = pd.date_range(start=start_date, end=end_date, freq='D')
            report = pd.DataFrame({
                'return': 0.0,
                'bench': 0.0
            }, index=date_range)

        # 构建持仓
        if positions_list:
            positions = pd.DataFrame(positions_list)
        else:
            positions = pd.DataFrame()

        logger.info(f"简化回测完成: {len(report)} 天, {len(positions)} 条持仓记录")

        return report, positions

    except Exception as e:
        logger.error(f"简化回测也失败了: {e}", exc_info=True)

        # 返回空结果
        date_range = pd.date_range(start=start_date, end=end_date, freq='D')
        report = pd.DataFrame({
            'return': 0.0,
            'bench': 0.0
        }, index=date_range)
        positions = pd.DataFrame()

        return report, positions


def print_analysis(analysis: Dict):
    """打印分析结果"""
    print("\n" + "=" * 80)
    print("回测分析报告")
    print("=" * 80)

    # 辅助函数：安全格式化
    def safe_format(value, fmt_type='percent', decimals=2):
        """安全格式化值"""
        if isinstance(value, (pd.Series, np.ndarray)):
            if len(value) > 0:
                value = value.iloc[0] if isinstance(value, pd.Series) else value[0]
            else:
                return "N/A"

        if pd.isna(value) or value is None:
            return "N/A"

        try:
            if fmt_type == 'percent':
                return f"{value:.{decimals}%}"
            else:
                return f"{value:.{decimals}f}"
        except:
            return str(value)

    # 收益相关
    print("\n📊 收益指标:")
    if 'total_return' in analysis:
        val = analysis['total_return']
        if not isinstance(val, str):
            print(f"  总收益率: {safe_format(val, 'percent', 2)}")
        else:
            print(f"  总收益率: {val}")
    if 'bench_return' in analysis:
        val = analysis['bench_return']
        if not isinstance(val, str):
            print(f"  基准收益: {safe_format(val, 'percent', 2)}")
        else:
            print(f"  基准收益: {val}")
    if 'excess_return' in analysis:
        val = analysis['excess_return']
        if not isinstance(val, str):
            print(f"  超额收益: {safe_format(val, 'percent', 2)}")
        else:
            print(f"  超额收益: {val}")

    # 风险指标
    print("\n⚠️  风险指标:")
    if 'annualized_return' in analysis:
        val = analysis['annualized_return']
        if not isinstance(val, str):
            print(f"  年化收益: {safe_format(val, 'percent', 2)}")
        else:
            print(f"  年化收益: {val}")
    if 'max_drawdown' in analysis:
        val = analysis['max_drawdown']
        if not isinstance(val, str):
            print(f"  最大回撤: {safe_format(val, 'percent', 2)}")
        else:
            print(f"  最大回撤: {val}")
    if 'volatility' in analysis:
        val = analysis['volatility']
        if not isinstance(val, str):
            print(f"  波动率: {safe_format(val, 'percent', 2)}")
        else:
            print(f"  波动率: {val}")

    # 风险调整收益
    print("\n📈 风险调整收益:")
    if 'sharpe' in analysis:
        val = analysis['sharpe']
        if not isinstance(val, str):
            print(f"  夏普比率: {safe_format(val, 'number', 4)}")
        else:
            print(f"  夏普比率: {val}")
    if 'information_ratio' in analysis:
        val = analysis['information_ratio']
        if not isinstance(val, str):
            print(f"  信息比率: {safe_format(val, 'number', 4)}")
        else:
            print(f"  信息比率: {val}")
    if 'calmar' in analysis:
        val = analysis['calmar']
        if not isinstance(val, str):
            print(f"  卡玛比率: {safe_format(val, 'number', 4)}")
        else:
            print(f"  卡玛比率: {val}")

    print("\n" + "=" * 80)


def save_results(
    report: pd.DataFrame,
    positions: pd.DataFrame,
    analysis: Dict,
    config: BacktestConfig
):
    """保存回测结果"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = config.output_dir / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"\n保存结果到: {output_dir}")

    # 保存报告
    if config.save_report:
        report_path = output_dir / 'report.csv'
        report.to_csv(report_path)
        logger.info(f"  报告: {report_path}")

    # 保存持仓
    if config.save_positions:
        # 检查 positions 是否为空
        if isinstance(positions, pd.DataFrame):
            has_data = not positions.empty
        elif isinstance(positions, dict):
            has_data = len(positions) > 0
        else:
            has_data = False

        if has_data:
            positions_path = output_dir / 'positions.csv'
            if isinstance(positions, pd.DataFrame):
                positions.to_csv(positions_path)
                logger.info(f"  持仓: {positions_path}")
            elif isinstance(positions, dict):
                # dict 是复杂对象，跳过或转换为简单格式
                logger.info(f"  持仓: dict 格式，跳过CSV保存")
                # 可选：保存为 json
                import json
                json_path = output_dir / 'positions.json'
                with open(json_path, 'w', encoding='utf-8') as f:
                    # 转换为可序列化的格式，需要处理 Timestamp 键
                    positions_simple = {}
                    for k, v in positions.items():
                        # 转换键为字符串
                        key = str(k) if not isinstance(k, str) else k
                        if isinstance(v, (pd.Series, pd.DataFrame)):
                            positions_simple[key] = v.tolist() if isinstance(v, pd.Series) else v.to_dict()
                        else:
                            positions_simple[key] = v
                    json.dump(positions_simple, f, indent=2, default=str)
                logger.info(f"  持仓(JSON): {json_path}")
            else:
                logger.info(f"  持仓: 未知格式，跳过保存")

    # 保存分析结果
    analysis_path = output_dir / 'analysis.yaml'
    with open(analysis_path, 'w', encoding='utf-8') as f:
        # 转换 numpy 类型为 Python 原生类型
        analysis_serializable = {}
        for k, v in analysis.items():
            if isinstance(v, (np.integer, np.floating)):
                analysis_serializable[k] = float(v)
            elif isinstance(v, np.ndarray):
                analysis_serializable[k] = v.tolist()
            else:
                analysis_serializable[k] = v

        yaml.dump(analysis_serializable, f, allow_unicode=True)
    logger.info(f"  分析: {analysis_path}")

    # 保存配置
    config_path = output_dir / 'config.yaml'
    config_dict = {
        'topk': config.topk,
        'n_drop': config.n_drop,
        'strategy_type': config.strategy_type,
        'start_date': str(config.start_date) if config.start_date else None,
        'end_date': str(config.end_date) if config.end_date else None,
        'exchange': config.exchange,
    }
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config_dict, f)
    logger.info(f"  配置: {config_path}")

    # 生成可视化
    if config.generate_plots:
        try:
            generate_plots(report, analysis, output_dir)
        except Exception as e:
            logger.warning(f"生成图表失败: {e}")

    return output_dir


def generate_plots(report: pd.DataFrame, analysis: Dict, output_dir: Path):
    """生成回测可视化图表"""
    try:
        import matplotlib.pyplot as plt
        import matplotlib
        matplotlib.use('Agg')  # 非交互式后端

        # 设置中文字体
        plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei']
        plt.rcParams['axes.unicode_minus'] = False

        # 1. 累计收益曲线
        if 'return' in report.columns:
            fig, ax = plt.subplots(figsize=(12, 6))

            # 策略收益
            cum_return = (1 + report['return']).cumprod()
            ax.plot(cum_return.index, cum_return.values, label='策略', linewidth=2)

            # 基准收益
            if 'bench' in report.columns:
                cum_bench = (1 + report['bench']).cumprod()
                ax.plot(cum_bench.index, cum_bench.values, label='基准', linewidth=2, alpha=0.7)

            ax.set_xlabel('日期', fontsize=12)
            ax.set_ylabel('累计收益', fontsize=12)
            ax.set_title('策略累计收益曲线', fontsize=14, fontweight='bold')
            ax.legend(fontsize=10)
            ax.grid(True, alpha=0.3)

            plt.tight_layout()
            plt.savefig(output_dir / 'cumulative_return.png', dpi=150, bbox_inches='tight')
            plt.close()
            logger.info(f"  图表: cumulative_return.png")

        # 2. 回撤曲线
        if 'return' in report.columns:
            fig, ax = plt.subplots(figsize=(12, 6))

            cum_return = (1 + report['return']).cumprod()
            running_max = cum_return.cummax()
            drawdown = (cum_return - running_max) / running_max

            ax.fill_between(drawdown.index, drawdown.values, 0, alpha=0.3, color='red')
            ax.plot(drawdown.index, drawdown.values, color='red', linewidth=1)

            ax.set_xlabel('日期', fontsize=12)
            ax.set_ylabel('回撤', fontsize=12)
            ax.set_title('策略回撤曲线', fontsize=14, fontweight='bold')
            ax.grid(True, alpha=0.3)

            plt.tight_layout()
            plt.savefig(output_dir / 'drawdown.png', dpi=150, bbox_inches='tight')
            plt.close()
            logger.info(f"  图表: drawdown.png")

    except ImportError:
        logger.warning("matplotlib 未安装，跳过图表生成")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Qlib 策略回测工具",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # 策略参数
    parser.add_argument('--topk', type=int, default=30, help='持仓数量 (默认: 30)')
    parser.add_argument('--n-drop', type=int, default=3, help='调仓时卖出数量 (默认: 3)')
    parser.add_argument('--strategy-type', default='topk_dropout',
                       choices=['topk_dropout', 'topk', 'soft_topk'], help='策略类型')

    # 日期参数
    parser.add_argument('--start', help='回测开始日期 (YYYY-MM-DD)')
    parser.add_argument('--end', help='回测结束日期 (YYYY-MM-DD)')

    # 交易所参数
    parser.add_argument('--exchange', default='SH', help='交易所 (默认: SH)')

    # 配置文件
    parser.add_argument('--config', help='回测配置文件 (YAML)')
    parser.add_argument('--manager-config', default='config/online_config.yaml',
                       help='Manager 配置文件')

    # 输出参数
    parser.add_argument('--output-dir', default='data/backtest', help='输出目录')
    parser.add_argument('--no-save', action='store_true', help='不保存结果')
    parser.add_argument('--no-plots', action='store_true', help='不生成图表')

    args = parser.parse_args()

    try:
        # 1. 加载配置
        if args.config:
            config_dict = load_config_from_yaml(args.config)
            config = BacktestConfig(**config_dict)
        else:
            config = BacktestConfig(
                topk=args.topk,
                n_drop=args.n_drop,
                strategy_type=args.strategy_type,
                start_date=args.start,
                end_date=args.end,
                exchange=args.exchange,
                output_dir=args.output_dir,
                save_report=not args.no_save,
                save_positions=not args.no_save,
                generate_plots=not args.no_plots,
                manager_config=args.manager_config,
            )

        # 2. 初始化 Manager
        logger.info("=" * 80)
        logger.info("初始化 ManagedOnlineManager")
        logger.info("=" * 80)

        manager = ManagedOnlineManager(
            config_path=config.manager_config,
            log_dir=str(config.output_dir / 'logs')
        )

        logger.info("Manager 初始化成功")

        # 3. 执行回测
        report, positions, analysis = run_backtest(manager, config)

        # 4. 打印分析结果
        print_analysis(analysis)

        # 5. 保存结果
        if config.save_report or config.save_positions:
            output_dir = save_results(report, positions, analysis, config)
            logger.info(f"\n✅ 回测完成！结果已保存到: {output_dir}")

    except KeyboardInterrupt:
        logger.info("\n用户中断")
        sys.exit(1)
    except Exception as e:
        logger.error(f"回测失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
