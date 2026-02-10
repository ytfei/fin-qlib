# Copyright (c) 2024
# Licensed under the MIT License.

"""
自定义 Handler（因子）示例

展示如何创建自定义因子处理器，并将其集成到策略中。
"""

from qlib.data.dataset.processor import Processor
from qlib.contrib.data.handler import Alpha158
import pandas as pd
import numpy as np


class CustomAlpha158(Alpha158):
    """
    自定义 Alpha158 的子类

    在 Alpha158 的基础上添加自定义因子
    """

    def __init__(self, instruments="csi300", start_time=None, end_time=None,
                 fit_start_time=None, fit_end_time=None, **kwargs):
        # 调用父类初始化
        super().__init__(
            instruments=instruments,
            start_time=start_time,
            end_time=end_time,
            fit_start_time=fit_start_time,
            fit_end_time=fit_end_time,
            **kwargs
        )


class CustomFactorHandler(Alpha158):
    """
    自定义因子处理器

    完全自定义的因子计算逻辑
    """

    def __init__(self, instruments="csi300", start_time=None, end_time=None,
                 fit_start_time=None, fit_end_time=None,
                 factor_config: dict = None):
        """
        Args:
            instruments: 股票池
            factor_config: 因子配置
                {
                    "momentum": {"window": [5, 10, 20]},
                    "volatility": {"window": [10, 30]},
                    ...
                }
        """
        super().__init__(
            instruments=instruments,
            start_time=start_time,
            end_time=end_time,
            fit_start_time=fit_start_time,
            fit_end_time=fit_end_time
        )
        self.factor_config = factor_config or {}


class MultiStyleFactorHandler(Processor):
    """
    多风格因子处理器

    支持多种风格的因子：
    - 动量因子
    - 反转因子
    - 波动率因子
    - 价值因子
    - 质量因子
    """

    def __init__(self, fit_start_time, fit_end_time,
                 styles: list = None,
                 **kwargs):
        """
        Args:
            fit_start_time: 训练开始时间
            fit_end_time: 训练结束时间
            styles: 要计算的因子风格列表
                ['momentum', 'reversal', 'volatility', 'value', 'quality']
        """
        super().__init__(fit_start_time=fit_start_time, fit_end_time=fit_end_time)
        self.styles = styles or ['momentum', 'volatility']

    def __call__(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算因子

        Args:
            df: 原始数据 (包含 OHLCV 等字段)

        Returns:
            添加了因子的 DataFrame
        """
        # 确保有必要的列
        required_cols = ['open', 'high', 'low', 'close', 'volume', 'vwap']
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")

        # 计算各类因子
        if 'momentum' in self.styles:
            df = self._add_momentum_factors(df)

        if 'reversal' in self.styles:
            df = self._add_reversal_factors(df)

        if 'volatility' in self.styles:
            df = self._add_volatility_factors(df)

        if 'value' in self.styles:
            df = self._add_value_factors(df)

        if 'quality' in self.styles:
            df = self._add_quality_factors(df)

        return df

    def _add_momentum_factors(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加动量因子"""
        # 5日收益率
        df['momentum_5d'] = df['close'].pct_change(5)

        # 20日收益率
        df['momentum_20d'] = df['close'].pct_change(20)

        # 60日收益率
        df['momentum_60d'] = df['close'].pct_change(60)

        # 动量加速度（20日动量 - 60日动量）
        df['momentum_accel'] = df['momentum_20d'] - df['momentum_60d']

        return df

    def _add_reversal_factors(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加反转因子"""
        # 5日反转（短期负收益）
        df['reversal_5d'] = -df['close'].pct_change(5)

        # 10日反转
        df['reversal_10d'] = -df['close'].pct_change(10)

        # 成交量反转
        df['volume_reversal'] = -df['volume'].pct_change(5)

        return df

    def _add_volatility_factors(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加波动率因子"""
        # 5日波动率（滚动标准差）
        df['volatility_5d'] = df['close'].pct_change().rolling(5).std()

        # 20日波动率
        df['volatility_20d'] = df['close'].pct_change().rolling(20).std()

        # ATR (Average True Range) - 波动率指标
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = true_range.rolling(14).mean()

        # 波动率比率（短期/长期）
        df['vol_ratio'] = df['volatility_5d'] / (df['volatility_20d'] + 1e-6)

        return df

    def _add_value_factors(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加价值因子"""
        # 注意：这些因子通常需要基本面数据
        # 这里只是示例，实际使用时需要从数据源获取

        # 市净率倒数（假设已有数据）
        # df['bp'] = 1.0 / df['pb']

        # 市盈率倒数
        # df['ep'] = 1.0 / df['pe']

        # 市销率倒数
        # df['sp'] = 1.0 / df['ps']

        return df

    def _add_quality_factors(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加质量因子"""
        # 注意：这些因子需要财务数据

        # ROE (Return on Equity)
        # df['roe'] = ...

        # ROA (Return on Assets)
        # df['roa'] = ...

        # 负债率
        # df['debt_ratio'] = ...

        return df


class Alpha360Custom(Processor):
    """
    自定义 Alpha360 处理器

    基于 Alpha360 的逻辑，但可以自定义计算
    """

    def __init__(self, fit_start_time, fit_end_time, **kwargs):
        super().__init__(fit_start_time=fit_start_time, fit_end_time=fit_end_time)

    def __call__(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算 Alpha360 风格的因子

        参考: https://github.com/microsoft/qlib/blob/main/qlib/contrib/data/handler.py
        """
        # 这里简化实现，实际应该包含完整的 Alpha360 计算
        # 包括: 价格动量、成交量、波动率等 360 个因子

        # 示例：添加一些因子
        for i in [5, 10, 20, 30, 60]:
            # 收益率
            df[f'return_{i}d'] = df['close'].pct_change(i)

            # 成交量变化率
            df[f'volume_change_{i}d'] = df['volume'].pct_change(i)

            # 最高价涨幅
            df[f'high_gain_{i}d'] = (df['high'] - df['close'].shift(i)) / df['close'].shift(i)

            # 最低价跌幅
            df[f'low_drop_{i}d'] = (df['low'] - df['close'].shift(i)) / df['close'].shift(i)

        return df


# 使用示例
if __name__ == "__main__":
    # 示例1: 使用自定义的 Alpha158
    handler_config = {
        "class": "CustomAlpha158",
        "module_path": "examples.custom_handler_example",
    }

    # 示例2: 使用多风格因子
    multi_style_config = {
        "class": "MultiStyleFactorHandler",
        "module_path": "examples.custom_handler_example",
        "init_params": {
            "styles": ["momentum", "volatility", "reversal"]
        }
    }

    # 示例3: 在任务配置中使用
    task_template = {
        "model": {
            "class": "LGBModel",
            "module_path": "qlib.contrib.model.gbdt",
        },
        "dataset": {
            "class": "DatasetH",
            "module_path": "qlib.data.dataset",
            "kwargs": {
                "handler": multi_style_config,  # 使用自定义 handler
                "segments": {
                    "train": ("2020-01-01", "2022-01-01"),
                    "valid": ("2022-01-01", "2022-07-01"),
                    "test": ("2022-07-01", "2023-01-01"),
                }
            }
        }
    }
