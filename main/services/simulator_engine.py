from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation
from typing import Any


VALID_ACTIONS = {'BUY', 'SELL', 'HOLD'}


class SimulationError(ValueError):
    def __init__(self, message: str, code: str = 'simulation_error', status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status


def create_simulation_state(
    ticker: str,
    prices: list[dict[str, Any]],
    initial_cash: str | int | float | Decimal,
) -> dict[str, Any]:
    if len(prices) < 2:
        raise SimulationError(
            'Symulacja wymaga co najmniej dwoch dni notowan.',
            code='not_enough_data',
        )

    cash = _to_money(initial_cash)
    if cash <= 0:
        raise SimulationError(
            'Gotowka poczatkowa musi byc wieksza od zera.',
            code='invalid_initial_cash',
        )

    state = {
        'ticker': ticker,
        'prices': deepcopy(prices),
        'initial_cash': _money_to_string(cash),
        'cash': _money_to_string(cash),
        'shares': 0,
        'current_step': 0,
        'status': 'running',
        'history': [],
        'portfolio_history': [],
    }
    state['portfolio_history'].append(portfolio_snapshot(state))
    return state


def perform_action(
    state: dict[str, Any],
    action: str,
    shares: str | int | None = None,
) -> dict[str, Any]:
    if state.get('status') == 'finished':
        raise SimulationError(
            'Symulacja jest juz zakonczona.',
            code='simulation_finished',
            status=409,
        )

    normalized_action = (action or '').strip().upper()
    if normalized_action not in VALID_ACTIONS:
        raise SimulationError('Niepoprawna akcja.', code='invalid_action')

    share_count = _parse_shares(shares, normalized_action)
    current_day = get_current_day(state)
    price = _to_money(current_day['close'])
    cash = _to_money(state['cash'])
    owned_shares = int(state['shares'])

    if normalized_action == 'BUY':
        cost = price * share_count
        if cost > cash:
            raise SimulationError(
                'Brak wystarczajacej gotowki na zakup.',
                code='insufficient_cash',
            )
        cash -= cost
        owned_shares += share_count
    elif normalized_action == 'SELL':
        if share_count > owned_shares:
            raise SimulationError(
                'Nie masz tylu akcji do sprzedazy.',
                code='insufficient_shares',
            )
        cash += price * share_count
        owned_shares -= share_count

    state['cash'] = _money_to_string(cash)
    state['shares'] = owned_shares

    transaction = {
        'date': current_day['date'],
        'action': normalized_action,
        'shares': int(share_count),
        'price': _money_to_string(price),
        'cash_after': state['cash'],
        'portfolio_value_after': _money_to_string(_portfolio_value(cash, owned_shares, price)),
    }
    state['history'].append(transaction)

    next_step = int(state['current_step']) + 1
    if next_step >= len(state['prices']) - 1:
        state['current_step'] = len(state['prices']) - 1
        state['status'] = 'finished'
    else:
        state['current_step'] = next_step

    state['portfolio_history'].append(portfolio_snapshot(state))
    return state


def get_current_day(state: dict[str, Any]) -> dict[str, Any]:
    return state['prices'][int(state['current_step'])]


def portfolio_snapshot(state: dict[str, Any]) -> dict[str, Any]:
    current_day = get_current_day(state)
    cash = _to_money(state['cash'])
    shares = int(state['shares'])
    price = _to_money(current_day['close'])
    value = _portfolio_value(cash, shares, price)
    initial_cash = _to_money(state['initial_cash'])

    return {
        'date': current_day['date'],
        'cash': _money_to_string(cash),
        'shares': shares,
        'stock_price': _money_to_string(price),
        'open': current_day['open'],
        'high': current_day['high'],
        'low': current_day['low'],
        'close': current_day['close'],
        'volume': current_day['volume'],
        'portfolio_value': _money_to_string(value),
        'profit_loss': _money_to_string(value - initial_cash),
    }


def serialize_state(state: dict[str, Any]) -> dict[str, Any]:
    current_day = get_current_day(state)
    portfolio = portfolio_snapshot(state)
    serialized = {
        'ticker': state['ticker'],
        'total_days': len(state['prices']),
        'current_step': state['current_step'],
        'current_day': current_day,
        'ohlcv': current_day,
        'portfolio': portfolio,
        'cash': portfolio['cash'],
        'shares': portfolio['shares'],
        'portfolio_value': portfolio['portfolio_value'],
        'profit_loss': portfolio['profit_loss'],
        'history': state['history'],
        'transaction_history': state['history'],
        'portfolio_history': state['portfolio_history'],
        'finished': state['status'] == 'finished',
    }
    if serialized['finished']:
        serialized['summary'] = simulation_summary(state)
    return serialized


def simulation_summary(state: dict[str, Any]) -> dict[str, Any]:
    final_snapshot = portfolio_snapshot(state)
    initial_cash = _to_money(state['initial_cash'])
    first_price = _to_money(state['prices'][0]['close'])
    final_price = _to_money(get_current_day(state)['close'])
    buy_and_hold_shares = int(initial_cash // first_price)
    buy_and_hold_cash = initial_cash - Decimal(buy_and_hold_shares) * first_price
    buy_and_hold_value = _portfolio_value(buy_and_hold_cash, buy_and_hold_shares, final_price)
    action_counts = {
        'BUY': 0,
        'SELL': 0,
        'HOLD': 0,
    }
    for transaction in state.get('history', []):
        action_counts[transaction['action']] = action_counts.get(transaction['action'], 0) + 1

    final_value = _to_money(final_snapshot['portfolio_value'])
    return {
        'final_date': final_snapshot['date'],
        'final_portfolio_value': final_snapshot['portfolio_value'],
        'total_profit_loss': final_snapshot['profit_loss'],
        'transaction_count': len(state.get('history', [])),
        'action_counts': action_counts,
        'buy_and_hold_value': _money_to_string(buy_and_hold_value),
        'buy_and_hold_profit_loss': _money_to_string(buy_and_hold_value - initial_cash),
        'difference_vs_buy_and_hold': _money_to_string(final_value - buy_and_hold_value),
    }


def _parse_shares(value: str | int | None, action: str) -> int:
    if action == 'HOLD':
        return 0

    try:
        shares = int(value)
    except (TypeError, ValueError) as exc:
        raise SimulationError(
            'Liczba akcji musi byc liczba calkowita.',
            code='invalid_shares',
        ) from exc

    if shares <= 0:
        raise SimulationError(
            'Liczba akcji musi byc wieksza od zera.',
            code='invalid_shares',
        )

    return shares


def _portfolio_value(cash: Decimal, shares: int, price: Decimal) -> Decimal:
    return cash + Decimal(shares) * price


def _to_money(value: str | int | float | Decimal) -> Decimal:
    try:
        return Decimal(str(value)).quantize(Decimal('0.01'))
    except (InvalidOperation, ValueError) as exc:
        raise SimulationError(
            'Niepoprawna wartosc pieniezna.',
            code='invalid_money',
        ) from exc


def _money_to_string(value: Decimal) -> str:
    return str(value.quantize(Decimal('0.01')))
