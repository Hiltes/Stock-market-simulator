from __future__ import annotations

from typing import Any

import pandas as pd


FEATURE_COLUMNS = [
    'close_lag_1',
    'close_lag_2',
    'close_lag_3',
    'return_1',
    'ma_5',
    'ma_10',
    'volatility_5',
    'volume',
    'volume_change',
]


def build_feature_frame(prices: list[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(prices).copy()
    if frame.empty:
        return frame

    frame['date'] = pd.to_datetime(frame['date']).dt.strftime('%Y-%m-%d')
    for column in ['open', 'high', 'low', 'close', 'volume']:
        frame[column] = pd.to_numeric(frame[column], errors='coerce')

    frame = frame.sort_values('date').reset_index(drop=True)
    frame['close_lag_1'] = frame['close'].shift(1)
    frame['close_lag_2'] = frame['close'].shift(2)
    frame['close_lag_3'] = frame['close'].shift(3)
    frame['return_1'] = frame['close'].pct_change()
    frame['ma_5'] = frame['close'].rolling(window=5).mean()
    frame['ma_10'] = frame['close'].rolling(window=10).mean()
    frame['volatility_5'] = frame['return_1'].rolling(window=5).std()
    frame['volume_change'] = frame['volume'].pct_change()
    frame['target_close'] = frame['close'].shift(-1)
    frame['target_direction'] = (frame['target_close'] > frame['close']).astype(int)

    frame = frame.replace([float('inf'), float('-inf')], pd.NA)
    return frame.dropna(subset=FEATURE_COLUMNS + ['target_close', 'target_direction']).reset_index(drop=True)
