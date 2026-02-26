#!/usr/bin/env python
# Copyright (c) 2024
# Licensed under the MIT License.

"""
实用的股票预测API客户端。

功能：
1. 查询指定日期的预测结果
2. 获取Top N股票排行榜
3. 批量查询多个日期
4. 获取特定股票的预测历史
5. 导出预测结果到CSV

Usage:
    # 查询2025-01-10的预测结果，显示Top 20
    python scripts/prediction_api_client.py query --date 2025-01-10 --top 20

    # 查询特定股票的预测
    python scripts/prediction_api_client.py stock --code SH600000 --start 2025-01-01 --end 2025-01-10

    # 批量导出
    python scripts/prediction_api_client.py export --start 2025-01-01 --end 2025-01-10 --output predictions.csv

    # 查看服务状态
    python scripts/prediction_api_client.py status
"""

import argparse
import sys
import csv
from datetime import datetime
from typing import List, Dict, Optional
import requests


class PredictionClient:
    """股票预测API客户端"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        """
        初始化客户端

        Args:
            base_url: API服务器地址
        """
        self.base_url = base_url.rstrip('/')

    def check_health(self) -> Dict:
        """检查服务健康状态"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    def get_status(self) -> Dict:
        """获取服务状态"""
        try:
            response = requests.get(f"{self.base_url}/status", timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    def get_available_dates(self) -> List[str]:
        """获取可用日期列表"""
        try:
            response = requests.get(f"{self.base_url}/dates", timeout=10)
            response.raise_for_status()
            return response.json().get('dates', [])
        except Exception as e:
            print(f"获取日期列表失败: {e}")
            return []

    def get_predictions(self, date: str, top_n: Optional[int] = None) -> Optional[Dict]:
        """
        获取指定日期的预测结果

        Args:
            date: 日期 (YYYY-MM-DD)
            top_n: 返回Top N结果

        Returns:
            预测结果字典
        """
        try:
            params = {"date": date}
            if top_n is not None:
                params["top_n"] = top_n

            response = requests.get(
                f"{self.base_url}/predictions",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            print(f"HTTP错误: {e.response.status_code} - {e.response.json().get('detail', e)}")
            return None
        except Exception as e:
            print(f"获取预测结果失败: {e}")
            return None

    def get_batch_predictions(
        self,
        start_date: str,
        end_date: str,
        top_n: Optional[int] = None
    ) -> Optional[Dict]:
        """
        批量获取预测结果

        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            top_n: 每个日期返回Top N结果

        Returns:
            批量预测结果字典
        """
        try:
            params = {
                "start_date": start_date,
                "end_date": end_date
            }
            if top_n is not None:
                params["top_n"] = top_n

            response = requests.get(
                f"{self.base_url}/batch",
                params=params,
                timeout=60
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            print(f"HTTP错误: {e.response.status_code} - {e.response.json().get('detail', e)}")
            return None
        except Exception as e:
            print(f"获取批量预测结果失败: {e}")
            return None

    def get_stock_prediction(
        self,
        stock_code: str,
        start_date: str,
        end_date: str
    ) -> List[Dict]:
        """
        获取特定股票在日期范围内的预测

        Args:
            stock_code: 股票代码 (如 SH600000)
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)

        Returns:
            预测记录列表 [(date, score), ...]
        """
        # 获取批量预测
        batch_data = self.get_batch_predictions(start_date, end_date)

        if not batch_data:
            return []

        # 提取指定股票的数据
        results = []
        for date_pred in batch_data.get('predictions', []):
            date = date_pred['date']
            for pred in date_pred['predictions']:
                if pred['instrument'] == stock_code:
                    results.append({
                        'date': date,
                        'score': pred['score'],
                        'rank': pred.get('rank')
                    })
                    break

        return results


def print_header(title: str, width: int = 80):
    """打印标题"""
    print("\n" + "=" * width)
    print(f" {title}")
    print("=" * width)


def print_leaderboard(predictions: List[Dict], date: str, limit: int = 30):
    """打印排行榜"""
    print(f"\n📊 {date} 股票预测排行榜 (Top {limit})")
    print("-" * 80)
    print(f"{'排名':<6}{'股票代码':<15}{'预测得分':<15}{'备注'}")
    print("-" * 80)

    for i, pred in enumerate(predictions[:limit], 1):
        rank = pred.get('rank', i)
        instrument = pred['instrument']
        score = pred['score']

        # 添加标记
        remark = ""
        if rank <= 5:
            remark = "⭐ 强烈推荐"
        elif rank <= 10:
            remark = "👍 推荐"

        print(f"{rank:<6}{instrument:<15}{score:>12.6f}    {remark}")

    print("-" * 80)


def print_stock_history(results: List[Dict], stock_code: str):
    """打印股票预测历史"""
    print(f"\n📈 {stock_code} 预测历史")
    print("-" * 60)
    print(f"{'日期':<15}{'预测得分':<15}{'当日排名'}")
    print("-" * 60)

    for r in results:
        date = r['date']
        score = r['score']
        rank = r.get('rank', 'N/A')

        # 根据得分添加颜色标记
        if score > 0.01:
            remark = "📈"
        elif score < -0.01:
            remark = "📉"
        else:
            remark = "➡️"

        print(f"{date:<15}{score:>12.6f}    {rank} {remark}")

    print("-" * 60)


def export_to_csv(data: Dict, output_file: str):
    """导出预测结果到CSV"""
    try:
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # 写入标题
            writer.writerow(['日期', '排名', '股票代码', '预测得分'])

            # 写入数据
            for date_pred in data.get('predictions', []):
                date = date_pred['date']
                for pred in date_pred['predictions']:
                    writer.writerow([
                        date,
                        pred.get('rank', ''),
                        pred['instrument'],
                        pred['score']
                    ])

        print(f"✅ 数据已导出到: {output_file}")
    except Exception as e:
        print(f"❌ 导出失败: {e}")


def cmd_status(args):
    """查看服务状态"""
    client = PredictionClient(args.url)

    print_header("服务状态")

    # 健康检查
    print("\n1️⃣  健康检查")
    health = client.check_health()
    if 'error' in health:
        print(f"❌ 服务不可用: {health['error']}")
        return

    status = health.get('status', 'unknown')
    print(f"   状态: {status}")
    print(f"   管理器已加载: {'是' if health.get('manager_loaded') else '否'}")
    print(f"   当前时间: {health.get('current_time', 'N/A')}")
    print(f"   策略数量: {len(health.get('strategies', []))}")

    # 详细状态
    print("\n2️⃣  详细状态")
    status_detail = client.get_status()
    if 'error' not in status_detail:
        manager = status_detail.get('manager', {})
        print(f"   策略: {', '.join(manager.get('strategies', []))}")
        print(f"   信号可用: {'是' if manager.get('signals_available') else '否'}")

        available = status_detail.get('available_dates', {})
        print(f"\n3️⃣  可用日期")
        print(f"   总日期数: {available.get('count', 0)}")
        print(f"   首日: {available.get('first', 'N/A')}")
        print(f"   末日: {available.get('last', 'N/A')}")


def cmd_dates(args):
    """查看可用日期"""
    client = PredictionClient(args.url)

    print_header("可用日期列表")

    dates = client.get_available_dates()

    if not dates:
        print("❌ 没有可用日期")
        return

    print(f"\n总共有 {len(dates)} 个日期的数据\n")

    if args.limit:
        dates = dates[-args.limit:]

    for date in dates:
        print(f"  📅 {date}")


def cmd_query(args):
    """查询预测结果"""
    client = PredictionClient(args.url)

    print_header(f"查询预测结果: {args.date}")

    # 获取预测
    data = client.get_predictions(args.date, top_n=args.top)

    if not data:
        print(f"❌ 未找到 {args.date} 的预测结果")
        return

    # 显示统计信息
    print(f"\n📊 统计信息:")
    print(f"   日期: {data['date']}")
    print(f"   总预测数: {data['total_count']:,}")
    print(f"   返回结果: {len(data['predictions'])}")

    # 显示排行榜
    print_leaderboard(data['predictions'], args.date, limit=args.display or 30)

    # 导出
    if args.output:
        export_to_csv({'predictions': [{'date': args.date, 'predictions': data['predictions']}]}, args.output)


def cmd_stock(args):
    """查询特定股票"""
    client = PredictionClient(args.url)

    print_header(f"股票预测查询: {args.code}")

    results = client.get_stock_prediction(args.code, args.start, args.end)

    if not results:
        print(f"❌ 未找到 {args.code} 的预测数据")
        return

    print(f"\n查询时间段: {args.start} 至 {args.end}")
    print(f"找到 {len(results)} 条记录")

    # 打印历史
    print_stock_history(results, args.code)

    # 统计信息
    scores = [r['score'] for r in results]
    print(f"\n📊 统计:")
    print(f"   平均得分: {sum(scores) / len(scores):.6f}")
    print(f"   最高得分: {max(scores):.6f}")
    print(f"   最低得分: {min(scores):.6f}")


def cmd_export(args):
    """批量导出"""
    client = PredictionClient(args.url)

    print_header(f"批量导出: {args.start} 至 {args.end}")

    data = client.get_batch_predictions(args.start, args.end, top_n=args.top)

    if not data:
        print("❌ 导出失败")
        return

    total_dates = data.get('total_dates', 0)
    print(f"\n✅ 获取到 {total_dates} 个日期的数据")

    export_to_csv(data, args.output)


def main():
    parser = argparse.ArgumentParser(
        description="股票预测API客户端",
        formatter_class=argparse.RawDescriptionHelpFormatter
 )

    # 全局参数
    parser.add_argument(
        '--url',
        default='http://localhost:8000',
        help='API服务器地址 (默认: http://localhost:8000)'
    )

    # 子命令
    subparsers = parser.add_subparsers(dest='command', help='可用命令')

    # status 命令
    subparsers.add_parser('status', help='查看服务状态')

    # dates 命令
    parser_dates = subparsers.add_parser('dates', help='查看可用日期')
    parser_dates.add_argument('--limit', type=int, help='显示最近N个日期')

    # query 命令
    parser_query = subparsers.add_parser('query', help='查询指定日期的预测')
    parser_query.add_argument('--date', required=True, help='查询日期 (YYYY-MM-DD)')
    parser_query.add_argument('--top', type=int, help='获取Top N结果')
    parser_query.add_argument('--display', type=int, help='显示Top N结果 (默认30)')
    parser_query.add_argument('--output', help='导出到CSV文件')

    # stock 命令
    parser_stock = subparsers.add_parser('stock', help='查询特定股票')
    parser_stock.add_argument('--code', required=True, help='股票代码 (如 SH600000)')
    parser_stock.add_argument('--start', required=True, help='开始日期 (YYYY-MM-DD)')
    parser_stock.add_argument('--end', required=True, help='结束日期 (YYYY-MM-DD)')

    # export 命令
    parser_export = subparsers.add_parser('export', help='批量导出')
    parser_export.add_argument('--start', required=True, help='开始日期 (YYYY-MM-DD)')
    parser_export.add_argument('--end', required=True, help='结束日期 (YYYY-MM-DD)')
    parser_export.add_argument('--top', type=int, help='每个日期取Top N')
    parser_export.add_argument('--output', required=True, help='输出CSV文件')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # 执行命令
    if args.command == 'status':
        cmd_status(args)
    elif args.command == 'dates':
        cmd_dates(args)
    elif args.command == 'query':
        cmd_query(args)
    elif args.command == 'stock':
        cmd_stock(args)
    elif args.command == 'export':
        cmd_export(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
