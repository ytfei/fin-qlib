#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Helper module to load actual stock codes from instruments files.

This works around the issue where D.instruments(market='csi300') returns
['market', 'filter_pipe'] instead of actual stock codes.
"""

from pathlib import Path
from typing import List


def load_stock_list_from_file(market: str = 'csi300', data_dir: Path = None) -> List[str]:
    """
    Load unique stock codes from instruments file.

    Parameters
    ----------
    market : str
        Market name (csi300, csi500, etc.)
    data_dir : Path
        Qlib data directory. If None, uses default ~/.qlib/qlib_data/cn_data

    Returns
    -------
    List[str]
        List of unique stock codes
    """
    if data_dir is None:
        data_dir = Path('~/.qlib/qlib_data/cn_data').expanduser()
    else:
        data_dir = Path(data_dir).expanduser()

    instruments_file = data_dir / 'instruments' / f'{market}.txt'

    if not instruments_file.exists():
        raise FileNotFoundError(f'Instruments file not found: {instruments_file}')

    # Read file and extract unique stock codes
    stocks = set()
    with open(instruments_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                # Format: stock_code<TAB>start_date<TAB>end_date
                parts = line.split('\t')
                if parts:
                    stock_code = parts[0].strip()
                    if stock_code:
                        stocks.add(stock_code)

    return sorted(list(stocks))


def get_instruments_dict(market: str = 'csi300', data_dir: Path = None) -> dict:
    """
    Get instruments dict for use with Alpha158 handler.

    Returns a dict with actual stock codes that works around the
    D.instruments() issue.

    Parameters
    ----------
    market : str
        Market name (csi300, csi500, etc.)
    data_dir : Path
        Qlib data directory

    Returns
    -------
    dict
        Dict with 'market' key mapping to list of stock codes
    """
    stock_list = load_stock_list_from_file(market, data_dir)
    return {'market': stock_list}


if __name__ == '__main__':
    # Test the function
    stocks = load_stock_list_from_file('csi300')
    print(f'Loaded {len(stocks)} stocks from CSI300')
    print(f'First 10: {stocks[:10]}')
    print(f'Last 10: {stocks[-10:]}')
