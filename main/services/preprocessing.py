from __future__ import annotations

from typing import Any

import pandas as pd


DEFAULT_LOOKBACK_DAYS = 3


def moving_average_windows(lookback_days: int) -> tuple[int, int]:
    short_window = max(2, int(lookback_days))
    long_window = max(short_window + 1, short_window * 2)
    return short_window, long_window


def build_feature_columns(lookback_days: int = DEFAULT_LOOKBACK_DAYS) -> list[str]:
    short_window, long_window = moving_average_windows(lookback_days)
    return [
        *[f'close_lag_{index}' for index in range(1, lookback_days + 1)],
        'return_1',
        f'ma_{short_window}',
        f'ma_{long_window}',
        f'volatility_{short_window}',
        'volume',
        'volume_change',
    ]


FEATURE_COLUMNS = build_feature_columns()


def build_feature_frame(
    prices: list[dict[str, Any]],
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    include_target: bool = True,
) -> pd.DataFrame:
    frame = pd.DataFrame(prices).copy()
    if frame.empty:
        return frame

    feature_columns = build_feature_columns(lookback_days)
    short_window, long_window = moving_average_windows(lookback_days)

    frame['date'] = pd.to_datetime(frame['date']).dt.strftime('%Y-%m-%d')
    for column in ['open', 'high', 'low', 'close', 'volume']:
        frame[column] = pd.to_numeric(frame[column], errors='coerce')

    frame = frame.sort_values('date').reset_index(drop=True)

    for index in range(1, lookback_days + 1):
        frame[f'close_lag_{index}'] = frame['close'].shift(index)

    frame['return_1'] = frame['close'].pct_change()
    frame[f'ma_{short_window}'] = frame['close'].rolling(window=short_window).mean()
    frame[f'ma_{long_window}'] = frame['close'].rolling(window=long_window).mean()
    frame[f'volatility_{short_window}'] = frame['return_1'].rolling(window=short_window).std()
    frame['volume_change'] = frame['volume'].pct_change()

    if include_target:
        frame['target_close'] = frame['close'].shift(-1)
        frame['target_direction'] = (frame['target_close'] > frame['close']).astype(int)
        required_columns = feature_columns + ['target_close', 'target_direction']
    else:
        required_columns = feature_columns

    frame = frame.replace([float('inf'), float('-inf')], pd.NA)
    return frame.dropna(subset=required_columns).reset_index(drop=True)
