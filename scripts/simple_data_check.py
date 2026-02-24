#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Simple Qlib Data Range Checker

Quick check what data you actually have in Qlib.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import qlib
from qlib.data import D
import pandas as pd


def main():
    # Initialize Qlib
    print("Initializing Qlib...")
    qlib.init(provider_uri="~/.qlib/qlib_data/cn_data", region="cn")

    print("\n" + "=" * 80)
    print("Checking Available Data")
    print("=" * 80)

    # Get all markets
    try:
        # Try to get instruments from different markets
        markets = ['all', 'csi300', 'csi500', 'sse', 'szse']

        for market in markets:
            try:
                instruments = D.instruments(market=market)
                if instruments and len(instruments) > 0:
                    print(f"\n✓ Market '{market}': {len(instruments)} instruments")
                    print(f"  First 5: {list(instruments)[:5]}")
            except Exception as e:
                print(f"\n✗ Market '{market}': {e}")

    except Exception as e:
        print(f"\nError getting instruments: {e}")

    # Try to get data for a specific instrument
    print("\n" + "=" * 80)
    print("Testing Data Access")
    print("=" * 80)

    # Common stock codes
    test_stocks = ['sh.600000', 'sz.000001', 'sh.601318']

    for stock in test_stocks:
        print(f"\nTrying {stock}...")
        try:
            data = D.features(
                instruments=[stock],
                fields=["$close", "$volume"],
                start_time="2020-01-01",
                end_time="2026-12-31"
            )

            if data is not None and len(data) > 0:
                dates = data.index.get_level_values('datetime')
                min_date = dates.min()
                max_date = dates.max()
                count = len(dates.unique())

                print(f"  ✓ Data found!")
                print(f"    Date range: {min_date} to {max_date}")
                print(f"    Total records: {count}")
                print(f"    Sample data:\n{data.head(3)}")

                # Calculate recommended segments
                total_period = (max_date - min_date).days
                train_end = min_date + pd.Timedelta(days=int(total_period * 0.6))
                valid_end = min_date + pd.Timedelta(days=int(total_period * 0.8))

                print(f"\n  Recommended config:")
                print(f"    train: [{min_date.strftime('%Y-%m-%d')}, {train_end.strftime('%Y-%m-%d')}]")
                print(f"    valid: [{train_end.strftime('%Y-%m-%d')}, {valid_end.strftime('%Y-%m-%d')}]")
                print(f"    test:  [{valid_end.strftime('%Y-%m-%d')}, {max_date.strftime('%Y-%m-%d')}]")

                break  # Found data, no need to check more stocks
            else:
                print(f"  ✗ No data found")

        except Exception as e:
            print(f"  ✗ Error: {e}")

    print("\n" + "=" * 80)
    print("Check Complete")
    print("=" * 80)


if __name__ == "__main__":
    main()
