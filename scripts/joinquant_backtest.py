# -*- coding: utf-8 -*-
"""
聚宽回测策略 - 基于模型预测的 Top 5 选股策略

策略逻辑:
1. 每日开盘前调用 API server 获取预测信号
2. 选择预测分数最高的 5 只股票
3. 使用昨日收盘价作为买入价
4. 等权重配置持仓

Author: fin-qlib
Date: 2026-02-27
"""

# 导入函数库
from jqdata import *
import requests
import pandas as pd
from datetime import datetime, timedelta

# API 配置
API_BASE_URL = 'http://47.86.82.234:8000'  # API server 地址
API_TOKEN = 'y42BLi428QZXeY63'  # 如果设置了 token，在这里填写

# 全局配置
g.stock_pool = None  # 股票池
g.top_n = 5  # 持仓股票数量
g.max_position_ratio = 0.98  # 最大仓位比例（留一点现金）

# 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 防止未来函数
    set_option('avoid_future_data', True)

    log.info('='*60)
    log.info('AI 选股策略启动 - Top5 持仓策略')
    log.info('='*60)

    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')

    ### 股票池设定 ###
    # 获取所有沪深300成分股作为股票池
    g.stock_pool = get_index_stocks('000300.XSHG')
    log.info(f'股票池: 沪深300成分股，共 {len(g.stock_pool)} 只')

    ## 运行函数（reference_security为运行时间的参考标的）
    # 开盘前运行 - 获取预测信号并调仓
    run_daily(before_market_open, time='before_open', reference_security='000300.XSHG')
    # 收盘后运行 - 输出日志
    run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')


def get_predictions_from_api(date):
    """
    从 API server 获取指定日期的预测信号

    Args:
        date: 日期字符串，格式 'YYYY-MM-DD'

    Returns:
        DataFrame with columns: instrument, score, rank
    """
    try:
        # 构建 API URL
        url = f"{API_BASE_URL}/predictions"

        # 请求参数
        params = {
            'date': date,
            'top_n': 50  # 获取 top 50 用于后续过滤
        }

        # 设置 headers（如果有 token）
        headers = {}
        if API_TOKEN:
            headers['Authorization'] = f'Bearer {API_TOKEN}'

        # 发送请求
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()

        # 解析响应
        data = response.json()

        # 转换为 DataFrame
        predictions = pd.DataFrame(data['predictions'])

        log.info(f"API 返回 {len(predictions)} 条预测")

        return predictions

    except requests.exceptions.ConnectionError:
        log.error(f"无法连接到 API server: {API_BASE_URL}")
        return None
    except requests.exceptions.HTTPError as e:
        log.error(f"API 请求失败: {e}")
        return None
    except Exception as e:
        log.error(f"获取预测失败: {e}")
        return None


def convert_stock_code(code):
    """
    转换股票代码格式

    从 API 返回的格式 (如 SH600000) 转换为聚宽格式 (如 600000.XSHG)

    Args:
        code: API 格式的股票代码

    Returns:
        聚宽格式的股票代码
    """
    if code.startswith('SH'):
        return code[2:] + '.XSHG'
    elif code.startswith('SZ'):
        return code[2:] + '.XSHE'
    else:
        return code


def filter_predictions_in_pool(predictions, stock_pool):
    """
    过滤预测结果，只保留股票池中的股票

    Args:
        predictions: 预测结果 DataFrame
        stock_pool: 股票池列表

    Returns:
        过滤后的 DataFrame
    """
    if predictions is None or len(predictions) == 0:
        return pd.DataFrame()

    # 转换代码格式
    predictions['jq_code'] = predictions['instrument'].apply(convert_stock_code)

    # 过滤
    filtered = predictions[predictions['jq_code'].isin(stock_pool)]

    log.info(f"过滤后在股票池中的股票: {len(filtered)} 只")

    return filtered


## 开盘前运行函数
def before_market_open(context):
    """开盘前运行 - 获取预测信号并进行调仓"""

    # 输出运行时间
    log.info('='*60)
    log.info(f'函数运行时间(before_market_open): {context.current_dt}')

    # 获取上一个交易日日期
    # 在聚宽中，context.current_dt 是当前日期
    # 我们需要获取上一个交易日的预测
    prev_date = context.previous_date

    date_str = prev_date.strftime('%Y-%m-%d')
    log.info(f'获取 {date_str} 的预测信号')

    # 从 API 获取预测
    predictions = get_predictions_from_api(date_str)

    if predictions is None or len(predictions) == 0:
        log.warning('未获取到预测信号，今日不调仓')
        return

    # 过滤股票池
    predictions = filter_predictions_in_pool(predictions, g.stock_pool)

    if len(predictions) == 0:
        log.warning('过滤后无可用股票，今日不调仓')
        return

    # 选择 top N
    top_stocks = predictions.head(g.top_n)

    log.info(f"Top {g.top_n} 股票: ")
    for i, row in top_stocks.iterrows():
        jq_code = row['jq_code']
        score = row['score']
        log.info(f"  {i+1}. {jq_code}: {score:.6f}")

    # 调仓逻辑
    rebalance(context, top_stocks)


def rebalance(context, target_stocks):
    """
    调仓函数

    Args:
        context: 策略上下文
        target_stocks: 目标持仓股票 DataFrame
    """
    # 获取当前持仓
    current_positions = context.portfolio.positions

    # 目标持仓列表
    target_list = target_stocks['jq_code'].tolist()

    # 卖出不在目标列表中的股票
    for stock in current_positions:
        if stock not in target_list and current_positions[stock].closeable_amount > 0:
            log.info(f"卖出: {stock}")
            order_target(stock, 0)

    # 计算每只目标股票的仓位（等权重）
    total_value = context.portfolio.total_value
    target_value_per_stock = total_value * g.max_position_ratio / len(target_list)

    # 买入目标股票
    for stock in target_list:
        current_position = current_positions.get(stock, None)
        current_amount = current_position.closeable_amount if current_position else 0

        # 使用昨日收盘价作为买入价
        # 获取历史价格
        hist_data = get_bars(stock, count=1, unit='1d', fields=['close'], include_now=True)
        if hist_data is not None and len(hist_data) > 0:
            yesterday_close = hist_data['close'][-1]

            # 计算目标持仓数量
            target_amount = int(target_value_per_stock / yesterday_close / 100) * 100

            if target_amount > current_amount:
                # 需要买入
                to_buy = target_amount - current_amount
                if to_buy > 0:
                    log.info(f"买入: {stock}, 数量: {to_buy}, 价格: {yesterday_close:.2f}")
                    # 使用 order 按数量买入
                    order(stock, to_buy)

                    # 或者使用 order_value 按金额买入（会使用市价）
                    # order_value(stock, to_buy * yesterday_close)
            elif target_amount < current_amount:
                # 需要卖出
                to_sell = current_amount - target_amount
                if to_sell > 0:
                    log.info(f"调仓卖出: {stock}, 数量: {to_sell}")
                    order(stock, -to_sell)
        else:
            log.warning(f"无法获取 {stock} 的价格数据")


## 收盘后运行函数
def after_market_close(context):
    """收盘后运行 - 输出日志"""
    log.info('='*60)
    log.info(f'收盘后运行时间: {context.current_dt.time()}')

    # 输出持仓信息
    portfolio = context.portfolio
    log.info(f'总资产: {portfolio.total_value:.2f}')
    log.info(f'持仓市值: {portfolio.positions_value:.2f}')
    log.info(f'可用资金: {portfolio.available_cash:.2f}')
    log.info(f'持仓数量: {len(portfolio.positions)}')

    log.info('当前持仓:')
    for stock, position in portfolio.positions.items():
        if position.closeable_amount > 0:
            log.info(f"  {stock}: {position.closeable_amount} 股, "
                    f"成本: {position.avg_cost:.2f}, "
                    f"现价: {position.price:.2f}, "
                    f"盈亏: {(position.price - position.avg_cost) / position.avg_cost * 100:.2f}%")

    # 得到当天所有成交记录
    trades = get_trades()
    if len(trades) > 0:
        log.info('今日成交记录:')
        for trade in trades.values():
            log.info(f'  {trade.security}: {trade.side} {trade.amount} 股 '
                    f'@ {trade.price:.2f}')
    else:
        log.info('今日无成交')

    log.info('='*60)
    log.info('一日结束')
    log.info('='*60)
