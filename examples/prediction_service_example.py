#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PredictionService 使用示例

展示如何直接使用 PredictionService 进行预测查询。
"""

from fqlib.prediction_service import PredictionService
import pandas as pd


def main():
    print("=" * 80)
    print("PredictionService 使用示例")
    print("=" * 80)

    # 1. 初始化服务
    print("\n1️⃣  初始化 PredictionService")
    print("-" * 80)

    service = PredictionService(
        config_path="config/online_config.yaml",
        log_dir="data/logs"
    )

    print("✅ PredictionService 初始化成功")

    # 2. 获取可用日期
    print("\n2️⃣  获取可用日期")
    print("-" * 80)

    dates = service.get_available_dates()
    print(f"总共有 {len(dates)} 个日期的预测数据")
    if dates:
        print(f"首日: {dates[0]}")
        print(f"末日: {dates[-1]}")

    # 3. 查询指定日期的预测
    if dates:
        target_date = dates[-1]  # 使用最新日期

        print(f"\n3️⃣  查询 {target_date} 的预测结果")
        print("-" * 80)

        # 获取Top 20预测
        predictions = service.get_predictions(target_date, top_n=20)

        print(f"\n📊 {target_date} Top 20 预测:")
        print(f"{'排名':<8}{'股票代码':<15}{'预测得分':<15}")
        print("-" * 40)

        for _, row in predictions.iterrows():
            rank = row.get('rank', _)
            instrument = row['instrument']
            score = row['score']
            print(f"{rank:<8}{instrument:<15}{score:>12.6f}")

    # 4. 查询特定股票的历史预测
    print("\n4️⃣  查询特定股票的历史预测")
    print("-" * 80)

    stock_code = "SH600000"  # 浦发银行

    # 获取所有预测数据中该股票的记录
    all_predictions = service.get_predictions(dates[-1])  # 获取最新一天的所有预测

    if stock_code in all_predictions['instrument'].values:
        stock_score = all_predictions[all_predictions['instrument'] == stock_code]['score'].values[0]
        print(f"{stock_code} 最新预测得分: {stock_score:.6f}")
    else:
        print(f"未找到 {stock_code} 的预测数据")

    # 5. 获取模型信息
    print("\n5️⃣  模型信息")
    print("-" * 80)

    model_info = service.get_model_info()
    print(f"策略数量: {model_info.get('n_strategies', 0)}")
    print(f"策略列表: {', '.join(model_info.get('strategies', []))}")
    print(f"当前时间: {model_info.get('cur_time', 'N/A')}")

    if model_info.get('signals_available'):
        print(f"信号数量: {model_info.get('signal_count', 0):,}")
        print(f"日期范围: {model_info.get('signal_start')} 至 {model_info.get('signal_end')}")

    # 6. 批量查询示例
    if len(dates) >= 3:
        print("\n6️⃣  批量查询最近3天的预测")
        print("-" * 80)

        start_date = dates[-3]
        end_date = dates[-1]

        batch_results = service.batch_get_predictions(
            start_date=start_date,
            end_date=end_date,
            top_n=5
        )

        for date, df in batch_results.items():
            print(f"\n{date} Top 5:")
            for _, row in df.iterrows():
                print(f"  {row['instrument']}: {row['score']:.6f}")

    print("\n" + "=" * 80)
    print("示例运行完成")
    print("=" * 80)


if __name__ == "__main__":
    main()
