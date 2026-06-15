from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any


SUPPORTED_TICKERS = {'AAPL', 'TSLA', 'MSFT', 'NVDA'}


class StockDataError(ValueError):
    def __init__(self, message: str, code: str = 'stock_data_error', status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status


def parse_date(value: str, field_name: str) -> date:
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (TypeError, ValueError) as exc:
        raise StockDataError(
            f'Niepoprawna data w polu {field_name}.',
            code='invalid_date',
        ) from exc


def validate_stock_request(ticker: str, start_date: str, end_date: str) -> tuple[str, date, date]:
    normalized_ticker = (ticker or '').strip().upper()
    if normalized_ticker not in SUPPORTED_TICKERS:
        raise StockDataError('Nieobslugiwany ticker.', code='invalid_ticker')

    parsed_start = parse_date(start_date, 'start_date')
    parsed_end = parse_date(end_date, 'end_date')

    if parsed_start >= parsed_end:
        raise StockDataError(
            'Data poczatkowa musi byc wczesniejsza niz koncowa.',
            code='invalid_date_range',
        )

    return normalized_ticker, parsed_start, parsed_end


def load_stock_prices(ticker: str, start_date: str, end_date: str) -> list[dict[str, Any]]:
    normalized_ticker, parsed_start, parsed_end = validate_stock_request(ticker, start_date, end_date)
    prices = _download_stock_prices(normalized_ticker, parsed_start, parsed_end)

    if len(prices) < 2:
        raise StockDataError(
            'Zakres musi zawierac co najmniej dwa dni notowan.',
            code='not_enough_data',
        )

    return prices


def load_stock_prices_with_history(
    ticker: str,
    start_date: str,
    end_date: str,
    history_calendar_days: int,
) -> dict[str, Any]:
    normalized_ticker, parsed_start, parsed_end = validate_stock_request(ticker, start_date, end_date)
    history_start = parsed_start - timedelta(days=max(0, int(history_calendar_days)))
    all_prices = _download_stock_prices(normalized_ticker, history_start, parsed_end)
    simulation_prices = [
        price
        for price in all_prices
        if parsed_start.isoformat() <= price['date'] < parsed_end.isoformat()
    ]

    if len(simulation_prices) < 2:
        raise StockDataError(
            'Zakres musi zawierac co najmniej dwa dni notowan.',
            code='not_enough_data',
        )

    first_simulation_date = simulation_prices[0]['date']
    model_prices = [price for price in all_prices if price['date'] <= first_simulation_date]
    if len(simulation_prices) > 1:
        model_prices.extend(simulation_prices[1:])

    return {
        'ticker': normalized_ticker,
        'prices': simulation_prices,
        'model_prices': model_prices,
        'model_history_days': max(0, len(model_prices) - len(simulation_prices)),
    }


def _download_stock_prices(ticker: str, start_date: date, end_date: date) -> list[dict[str, Any]]:
    try:
        import yfinance as yf
    except ImportError as exc:
        raise StockDataError(
            'Brak biblioteki yfinance. Zainstaluj zaleznosci z requirements.txt.',
            code='missing_dependency',
            status=500,
        ) from exc

    frame = yf.download(
        ticker,
        start=start_date.isoformat(),
        end=end_date.isoformat(),
        auto_adjust=False,
        progress=False,
    )

    if frame.empty:
        raise StockDataError('Brak danych dla podanego zakresu.', code='no_data', status=404)

    if hasattr(frame.columns, 'nlevels') and frame.columns.nlevels > 1:
        frame.columns = frame.columns.get_level_values(0)

    required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
    missing_columns = [column for column in required_columns if column not in frame.columns]
    if missing_columns:
        raise StockDataError(
            'Pobrane dane nie zawieraja wymaganych kolumn.',
            code='missing_columns',
            status=500,
        )

    frame = frame.reset_index()
    frame = frame.dropna(subset=required_columns)
    frame = frame.sort_values('Date')

    prices = []
    for row in frame.to_dict(orient='records'):
        prices.append(
            {
                'date': _date_to_iso(row['Date']),
                'open': _to_decimal_string(row['Open']),
                'high': _to_decimal_string(row['High']),
                'low': _to_decimal_string(row['Low']),
                'close': _to_decimal_string(row['Close']),
                'volume': int(row['Volume']),
            }
        )

    return prices


def _date_to_iso(value: Any) -> str:
    if hasattr(value, 'date'):
        return value.date().isoformat()
    return str(value)


def _to_decimal_string(value: Any) -> str:
    return str(Decimal(str(value)).quantize(Decimal('0.01')))
