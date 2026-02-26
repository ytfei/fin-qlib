#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
每日预测信号获取脚本

用途：在交易日早上开盘前（如08:30）获取当日的预测信号

Usage:
    # 获取今天的预测
    python scripts/daily_fetch_prediction.py

    # 获取指定日期的预测
    python scripts/daily_fetch_prediction.py --date 2025-08-19

    # 获取Top 50预测
    python scripts/daily_fetch_prediction.py --top 50

    # 检查服务状态
    python scripts/daily_fetch_prediction.py --check
"""

import argparse
import sys
from datetime import datetime, timedelta

import requests


def print_header(title: str, width: int = 80):
    """打印标题"""
    print("\n" + "=" * width)
    print(f" {title}")
    print("=" * width)


def check_service(base_url: str) -> bool:
    """检查服务状态"""
    print_header("服务状态检查")

    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        response.raise_for_status()
        data = response.json()

        print(f"\n✅ 服务状态: {data['status']}")
        print(f"   管理器已加载: {data['manager_loaded']}")
        print(f"   当前时间: {data.get('current_time', 'N/A')}")
        print(f"   策略: {', '.join(data.get('strategies', []))}")

        return data['status'] == 'healthy'

    except Exception as e:
        print(f"\n❌ 服务不可用: {e}")
        return False


def get_available_dates(base_url: str) -> list:
    """获取可用日期列表"""
    try:
        response = requests.get(f"{base_url}/dates", timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get('dates', [])
    except Exception as e:
        print(f"❌ 获取日期列表失败: {e}")
        return []


def get_prediction(base_url: str, date: str, top_n: int = 20):
    """获取指定日期的预测"""
    print_header(f"获取 {date} 的预测信号 (Top {top_n})")

    try:
        params = {"date": date, "top_n": top_n}
        response = requests.get(f"{base_url}/predictions", params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        # 显示统计信息
        total = data['total_count']
        returned = len(data['predictions'])

        print(f"\n📊 统计信息:")
        print(f"   目标日期: {data['date']}")
        print(f"   总预测数: {total:,}")
        print(f"   返回结果: {returned}")

        # 显示Top预测
        display_count = min(top_n, len(data['predictions']))
        print(f"\n📈 Top {display_count} 预测:")
        print("-" * 80)
        print(f"{'排名':<8}{'股票代码':<15}{'预测得分':<15}{'信号强度'}")
        print("-" * 80)

        for pred in data['predictions'][:top_n]:
            rank = pred.get('rank', 0)
            instrument = pred['instrument']
            score = pred['score']

            # 信号强度判断
            if score > 0.02:
                strength = "⭐⭐⭐ 强烈买入"
            elif score > 0.01:
                strength = "⭐⭐ 买入"
            elif score > 0.005:
                strength = "⭐ 偏多"
            elif score > 0:
                strength = "➡️ 中性偏多"
            elif score > -0.005:
                strength = "➡️ 中性偏空"
            elif score > -0.01:
                strength = "⭐ 偏空"
            elif score > -0.02:
                strength = "⭐⭐ 卖出"
            else:
                strength = "⭐⭐⭐ 强烈卖出"

            print(f"{rank:<8}{instrument:<15}{score:>12.6f}    {strength}")

        print("-" * 80)

        # 数据说明
        print(f"\n📝 数据说明:")
        print(f"   • 预测目标日期: {date}")
        print(f"   • 数据截止日期: {get_previous_trading_day(date)}")
        print(f"   • 该预测是基于前一交易日收盘后的数据生成的")

        return data

    except requests.exceptions.HTTPError as e:
        error_data = e.response.json()
        print(f"\n❌ HTTP错误 {e.response.status_code}: {error_data.get('detail', error_data)}")

        # 如果日期不存在，提供建议
        if e.response.status_code == 404:
            dates = get_available_dates(base_url)
            if dates:
                print(f"\n💡 可用日期:")
                print(f"   首日: {dates[0]}")
                print(f"   末日: {dates[-1]}")
                if len(dates) <= 10:
                    print(f"   全部: {', '.join(dates)}")

        return None
    except Exception as e:
        print(f"\n❌ 获取预测失败: {e}")
        return None


def get_previous_trading_day(date_str: str) -> str:
    """
    获取前一交易日（简单实现，不处理节假日）

    Args:
        date_str: 日期字符串 YYYY-MM-DD

    Returns:
        前一日期字符串
    """
    date = datetime.strptime(date_str, "%Y-%m-%d")
    prev_day = date - timedelta(days=1)
    return prev_day.strftime("%Y-%m-%d")


def export_to_csv(data: dict, filename: str):
    """导出预测到CSV"""
    import csv

    try:
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['排名', '股票代码', '预测得分', '信号强度'])

            for pred in data['predictions']:
                rank = pred.get('rank', '')
                instrument = pred['instrument']
                score = pred['score']

                # 信号强度
                if score > 0.02:
                    strength = "强烈买入"
                elif score > 0.01:
                    strength = "买入"
                elif score > 0:
                    strength = "偏多"
                elif score > -0.01:
                    strength = "偏空"
                else:
                    strength = "卖出"

                writer.writerow([rank, instrument, f"{score:.6f}", strength])

        print(f"✅ 已导出到: {filename}")
    except Exception as e:
        print(f"❌ 导出失败: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="获取每日预测信号",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python scripts/daily_fetch_prediction.py                  # 获取今天预测
  python scripts/daily_fetch_prediction.py --date 2025-08-19  # 获取指定日期
  python scripts/daily_fetch_prediction.py --top 50        # 获取Top 50
  python scripts/daily_fetch_prediction.py --check         # 检查服务状态
        """
    )

    parser.add_argument(
        '--url',
        default='http://localhost:8000',
        help='API服务器地址'
    )

    parser.add_argument(
        '--date',
        help='目标日期 (YYYY-MM-DD)，默认为今天'
    )

    parser.add_argument(
        '--top',
        type=int,
        default=20,
        help='获取Top N预测 (默认: 20)'
    )

    parser.add_argument(
        '--output',
        help='导出到CSV文件'
    )

    parser.add_argument(
        '--check',
        action='store_true',
        help='仅检查服务状态'
    )

    args = parser.parse_args()

    # 确定目标日期
    if args.date:
        target_date = args.date
    else:
        target_date = datetime.now().strftime("%Y-%m-%d")

    # 打印欢迎信息
    print_header(f"每日预测信号获取 - {target_date}")

    # 检查服务
    if not check_service(args.url):
        print("\n❌ 服务不可用，请先启动API服务")
        sys.exit(1)

    # 如果只是检查状态，到此结束
    if args.check:
        print("\n✅ 服务状态检查完成")
        sys.exit(0)

    # 获取可用日期
    dates = get_available_dates(args.url)

    if not dates:
        print("\n❌ 没有可用的预测数据")
        print("   请先运行训练/预测流程")
        sys.exit(1)

    print(f"\n📅 可用日期范围: {dates[0]} 至 {dates[-1]}")

    # 检查目标日期是否可用
    if target_date not in dates:
        print(f"\n⚠️  目标日期 {target_date} 的预测不可用")

        # 建议使用最新可用日期
        latest_date = dates[-1]
        print(f"💡 建议使用最新可用日期: {latest_date}")

        response = input("是否使用最新日期? (Y/n): ")
        if response.lower() == 'n':
            print("已取消")
            sys.exit(0)

        target_date = latest_date

    # 获取预测
    data = get_prediction(args.url, target_date, args.top)

    if data and args.output:
        export_to_csv(data, args.output)

    print("\n" + "=" * 80)
    print("完成")
    print("=" * 80)


if __name__ == "__main__":
    main()
