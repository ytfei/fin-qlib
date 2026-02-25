#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查可用的股票池配置

Usage:
    python scripts/check_stock_pools.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import qlib
from qlib.data import D


def main():
    # 初始化 Qlib
    print("初始化 Qlib...")
    qlib.init(provider_uri="~/.qlib/qlib_data/cn_data", region="cn")

    print("\n" + "=" * 80)
    print("可用股票池配置")
    print("=" * 80)

    # 检查不同的市场
    markets = {
        'csi300': '沪深 300 指数成分股（大盘股）',
        'csi500': '中证 500 指数成分股（中盘股）',
        'all': '所有可用股票',
        'sse': '上海证券交易所',
        'szse': '深圳证券交易所',
    }

    for market, description in markets.items():
        try:
            insts = D.instruments(market=market)
            count = len(insts) if insts else 0

            print(f"\n📊 {market.upper()}")
            print(f"   描述: {description}")
            print(f"   数量: {count} 只股票")

            if count > 0:
                inst_list = list(insts)
                print(f"   示例: {', '.join(inst_list[:5])}")

                if count <= 20:
                    print(f"   全部: {', '.join(inst_list)}")
        except Exception as e:
            print(f"\n❌ {market}: 不可用")
            print(f"   错误: {e}")

    print("\n" + "=" * 80)
    print("配置建议")
    print("=" * 80)
    print("""
在配置文件中使用：

# 方式 1：使用预定义市场
handler:
  class: Alpha158
  instruments: "csi300"  # 或 csi500, all, sse, szse

# 方式 2：自定义股票列表
handler:
  class: Alpha158
  instruments: ["sh.600000", "sh.600036", "sz.000001"]

# 方式 3：从文件读取
handler:
  class: Alpha158
  instruments: "path/to/stocks.txt"
    """)


if __name__ == "__main__":
    main()
