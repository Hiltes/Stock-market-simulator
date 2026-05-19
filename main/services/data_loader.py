from dataclasses import dataclass
from datetime import date
import re

import pandas as pd
import yfinance as yf


TICKER_PATTERN = re.compile(r"^[A-Z0-9.-]{1,12}$")


@dataclass(frozen=True)
class StockPrice:
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


def fetch_stock_prices(ticker: str, start_date: str, end_date: str) -> list[StockPrice]:
    normalized_ticker = normalize_ticker(ticker)
    _validate_date_range(start_date, end_date)

    frame = yf.download(
        normalized_ticker,
        start=start_date,
        end=end_date,
        auto_adjust=False,
        progress=False,
    )

    if frame.empty:
        raise ValueError("No stock data returned for selected ticker and date range.")

    return stock_prices_from_frame(frame)


def normalize_ticker(ticker: str) -> str:
    normalized = ticker.strip().upper()
    if not TICKER_PATTERN.match(normalized):
        raise ValueError("Ticker contains unsupported characters.")
    return normalized


def stock_prices_from_frame(frame: pd.DataFrame) -> list[StockPrice]:
    data = frame.copy()
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    required_columns = ["Open", "High", "Low", "Close", "Volume"]
    missing_columns = [column for column in required_columns if column not in data.columns]
    if missing_columns:
        raise ValueError(f"Missing required stock columns: {', '.join(missing_columns)}")

    data = data.reset_index()
    data = data.dropna(subset=required_columns)
    prices = []

    for row in data.itertuples(index=False):
        prices.append(
            StockPrice(
                date=pd.Timestamp(getattr(row, "Date")).date(),
                open=round(float(getattr(row, "Open")), 2),
                high=round(float(getattr(row, "High")), 2),
                low=round(float(getattr(row, "Low")), 2),
                close=round(float(getattr(row, "Close")), 2),
                volume=int(getattr(row, "Volume")),
            )
        )

    if not prices:
        raise ValueError("Stock data has no complete OHLCV rows.")

    return prices


def _validate_date_range(start_date: str, end_date: str) -> None:
    start = pd.Timestamp(start_date).date()
    end = pd.Timestamp(end_date).date()

    if start >= end:
        raise ValueError("Start date must be earlier than end date.")
