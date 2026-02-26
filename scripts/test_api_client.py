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

import requests


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

    def __init__(self, base_url: str = "http://localhost:8000"):
        """
        初始化测试客户端

        Args:
            base_url: API服务器地址
        """
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()

    def test_health(self) -> bool:
        """测试健康检查"""
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=5)
            response.raise_for_status()
            data = response.json()

            print("\n✅ 健康检查通过")
            print(f"   状态: {data['status']}")
            print(f"   管理器已加载: {data['manager_loaded']}")
            print(f"   当前时间: {data.get('current_time', 'N/A')}")
            print(f"   策略: {', '.join(data.get('strategies', []))}")

            return data['status'] == 'healthy'

        except Exception as e:
            print(f"\n❌ 健康检查失败: {e}")
            return False

    def test_status(self) -> dict:
        """测试状态接口"""
        try:
            response = self.session.get(f"{self.base_url}/status", timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"❌ 获取状态失败: {e}")
            return {}

    def get_available_dates(self) -> List[str]:
        """获取可用日期列表"""
        try:
            response = self.session.get(f"{self.base_url}/dates", timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get('dates', [])
        except Exception as e:
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
            params = {"date": date}
            if top_n:
                params["top_n"] = top_n

            response = self.session.get(
                f"{self.base_url}/predictions",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as e:
            error_data = e.response.json()
            print(f"   ❌ HTTP错误 {e.response.status_code}: {error_data.get('detail', error_data)}")
            return None
        except Exception as e:
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
                returned = len(result['predictions'])
                top_preds = result.get('top_n', [])

                print(f"   ✅ 成功")
                print(f"   总预测数: {total:,}")
                print(f"   返回结果: {returned}")

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

        # 6. 总结
        print_header("测试总结")
        print(f"\n测试日期数: {sample_count}")
        print(f"成功: {success_count} ✅")
        print(f"失败: {fail_count} ❌")
        print(f"成功率: {success_count / sample_count * 100:.1f}%")

        if success_count == sample_count:
            print("\n🎉 所有测试通过！")
        else:
            print(f"\n⚠️  有 {fail_count} 个测试失败")


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

    # 创建测试器
    tester = APITester(base_url=args.url)

    # 运行测试
    try:
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
