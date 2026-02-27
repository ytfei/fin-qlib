#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
API测试客户端 - 随机测试预测结果

这个脚本会：
1. 连接到API服务
2. 获取可用日期列表
3. 随机选择几个日期
4. 查询这些日期的预测结果
5. 显示预测统计信息

Usage:
    python scripts/test_api_client.py
    python scripts/test_api_client.py --url http://localhost:8000 --samples 5
"""

import argparse
import sys
import random
from typing import List

from fqlib.api_client import StockPredictionClient, HTTPError, ConnectionError


def print_header(title: str, width: int = 80):
    """打印标题"""
    print("\n" + "=" * width)
    print(f" {title}")
    print("=" * width)


def print_subheader(title: str, width: int = 80):
    """打印子标题"""
    print("\n" + "-" * width)
    print(f" {title}")
    print("-" * width)


class APITester:
    """API测试客户端"""

    def __init__(self, base_url: str = "http://localhost:8000", api_token: str = None):
        """
        初始化测试客户端

        Args:
            base_url: API服务器地址
            api_token: API认证token（可选）
        """
        self.client = StockPredictionClient(base_url, api_token=api_token)

    def test_health(self) -> bool:
        """测试健康检查"""
        try:
            health = self.client.health()

            print("\n✅ 健康检查通过")
            print(f"   状态: {health['status']}")
            print(f"   管理器已加载: {health['manager_loaded']}")
            print(f"   当前时间: {health.get('current_time', 'N/A')}")
            print(f"   策略: {', '.join(health.get('strategies', []))}")

            return health['status'] == 'healthy'

        except (ConnectionError, HTTPError) as e:
            print(f"\n❌ 健康检查失败: {e}")
            return False

    def test_status(self) -> dict:
        """测试状态接口"""
        try:
            return self.client.get_status()
        except (ConnectionError, HTTPError) as e:
            print(f"❌ 获取状态失败: {e}")
            return {}

    def get_available_dates(self) -> List[str]:
        """获取可用日期列表"""
        try:
            return self.client.get_available_dates()
        except (ConnectionError, HTTPError) as e:
            print(f"❌ 获取日期列表失败: {e}")
            return []

    def test_prediction(self, date: str, top_n: int = 10) -> dict:
        """
        测试指定日期的预测

        Args:
            date: 日期
            top_n: 获取Top N结果

        Returns:
            预测结果
        """
        try:
            return self.client.get_predictions(date, top_n=top_n)
        except HTTPError as e:
            print(f"   ❌ HTTP错误: {e}")
            return None
        except (ConnectionError, Exception) as e:
            print(f"   ❌ 请求失败: {e}")
            return None

    def run_random_tests(self, sample_count: int = 5, top_n: int = 20):
        """
        运行随机测试

        Args:
            sample_count: 随机测试的日期数量
            top_n: 每个日期获取Top N预测
        """
        print_header(f"随机预测测试 (随机选择 {sample_count} 个日期)")

        # 1. 健康检查
        if not self.test_health():
            print("\n❌ 服务不可用，无法继续测试")
            return

        # 2. 获取状态
        print_subheader("服务状态")
        status = self.test_status()
        if status:
            manager = status.get('manager', {})
            available = status.get('available_dates', {})

            print(f"\n策略数量: {manager.get('n_strategies', 0)}")
            print(f"策略: {', '.join(manager.get('strategies', []))}")
            print(f"可用日期数: {available.get('count', 0)}")
            print(f"日期范围: {available.get('first', 'N/A')} 至 {available.get('last', 'N/A')}")

        # 3. 获取可用日期
        print_subheader("获取可用日期")
        dates = self.get_available_dates()

        if not dates:
            print("❌ 没有可用的预测日期")
            return

        print(f"\n总共有 {len(dates)} 个日期的预测数据")

        # 4. 随机选择日期
        sample_count = min(sample_count, len(dates))
        selected_dates = random.sample(dates, sample_count)

        print(f"\n📅 随机选择 {sample_count} 个日期进行测试:")
        for i, date in enumerate(selected_dates, 1):
            print(f"   {i}. {date}")

        # 5. 测试每个日期的预测
        print_subheader("预测测试结果")

        success_count = 0
        fail_count = 0

        for i, date in enumerate(selected_dates, 1):
            print(f"\n📊 测试日期 {i}/{sample_count}: {date}")

            result = self.test_prediction(date, top_n=top_n)

            if result:
                success_count += 1

                # 显示统计信息
                total = result['total_count']
                predictions = result['predictions']
                top_preds = predictions[:10]

                print(f"   ✅ 成功")
                print(f"   总预测数: {total:,}")
                print(f"   返回结果: {len(predictions)}")

                # 显示Top 5
                if top_preds:
                    print(f"\n   Top 5 预测:")
                    for j, pred in enumerate(top_preds[:5], 1):
                        instrument = pred['instrument']
                        score = pred['score']
                        rank = pred.get('rank', j)
                        print(f"      {j}. {instrument}: {score:.6f} (排名: {rank})")
            else:
                fail_count += 1

        # 6. 测试汇总统计
        print_subheader("汇总统计测试")

        # 选择一个日期测试统计功能
        test_date = selected_dates[0]
        try:
            summary = self.client.get_prediction_summary(test_date)
            print(f"\n日期: {summary['date']}")
            print(f"总预测数: {summary['total_count']:,}")

            if summary['score_stats']:
                stats = summary['score_stats']
                print(f"\n分数统计:")
                print(f"  均值: {stats['mean']:.6f}")
                print(f"  标准差: {stats['std']:.6f}")
                print(f"  最小值: {stats['min']:.6f}")
                print(f"  最大值: {stats['max']:.6f}")
        except Exception as e:
            print(f"⚠️  无法获取汇总统计: {e}")

        # 7. 总结
        print_header("测试总结")
        print(f"\n测试日期数: {sample_count}")
        print(f"成功: {success_count} ✅")
        print(f"失败: {fail_count} ❌")
        print(f"成功率: {success_count / sample_count * 100:.1f}%")

        if success_count == sample_count:
            print("\n🎉 所有测试通过！")
        else:
            print(f"\n⚠️  有 {fail_count} 个测试失败")

    def close(self):
        """关闭客户端"""
        self.client.close()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="API测试客户端 - 随机测试预测结果"
    )

    parser.add_argument(
        '--url',
        default='http://localhost:8000',
        help='API服务器地址 (默认: http://localhost:8000)'
    )

    parser.add_argument(
        '--api-token',
        default=None,
        help='API认证token（可选）'
    )

    parser.add_argument(
        '--samples',
        type=int,
        default=5,
        help='随机测试的日期数量 (默认: 5)'
    )

    parser.add_argument(
        '--top-n',
        type=int,
        default=20,
        help='每个日期获取Top N预测 (默认: 20)'
    )

    parser.add_argument(
        '--seed',
        type=int,
        help='随机种子（用于可重复测试）'
    )

    args = parser.parse_args()

    # 设置随机种子
    if args.seed:
        random.seed(args.seed)
        print(f"使用随机种子: {args.seed}")

    # 使用 context manager 创建测试器
    try:
        with APITester(base_url=args.url, api_token=args.api_token) as tester:
            tester.run_random_tests(sample_count=args.samples, top_n=args.top_n)

    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
