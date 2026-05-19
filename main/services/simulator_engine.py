from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation
from typing import Any


VALID_ACTIONS = {'BUY', 'SELL', 'HOLD'}


class SimulationError(ValueError):
    pass


def create_simulation_state(
    ticker: str,
    prices: list[dict[str, Any]],
    initial_cash: str | int | float | Decimal,
) -> dict[str, Any]:
    if len(prices) < 2:
        raise SimulationError('Symulacja wymaga co najmniej dwóch dni notowań.')

    cash = _to_money(initial_cash)
    if cash <= 0:
        raise SimulationError('Gotówka początkowa musi być większa od zera.')

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
        raise SimulationError('Symulacja jest już zakończona.')

    normalized_action = (action or '').strip().upper()
    if normalized_action not in VALID_ACTIONS:
        raise SimulationError('Niepoprawna akcja.')

    share_count = _parse_shares(shares, normalized_action)
    current_day = get_current_day(state)
    price = _to_money(current_day['close'])
    cash = _to_money(state['cash'])
    owned_shares = int(state['shares'])

    if normalized_action == 'BUY':
        cost = price * share_count
        if cost > cash:
            raise SimulationError('Brak wystarczającej gotówki na zakup.')
        cash -= cost
        owned_shares += share_count
    elif normalized_action == 'SELL':
        if share_count > owned_shares:
            raise SimulationError('Nie masz tylu akcji do sprzedazy.')
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
    return {
        'ticker': state['ticker'],
        'current_step': state['current_step'],
        'current_day': get_current_day(state),
        'portfolio': portfolio_snapshot(state),
        'history': state['history'],
        'portfolio_history': state['portfolio_history'],
        'finished': state['status'] == 'finished',
    }


def _parse_shares(value: str | int | None, action: str) -> int:
    if action == 'HOLD':
        return 0

    try:
        shares = int(value)
    except (TypeError, ValueError) as exc:
        raise SimulationError('Liczba akcji musi być liczbą całkowitą.') from exc

    if shares <= 0:
        raise SimulationError('Liczba akcji musi być większa od zera.')

    return shares


def _portfolio_value(cash: Decimal, shares: int, price: Decimal) -> Decimal:
    return cash + Decimal(shares) * price


def _to_money(value: str | int | float | Decimal) -> Decimal:
    try:
        return Decimal(str(value)).quantize(Decimal('0.01'))
    except (InvalidOperation, ValueError) as exc:
        raise SimulationError('Niepoprawna wartość pieniężna.') from exc


def _money_to_string(value: Decimal) -> str:
    return str(value.quantize(Decimal('0.01')))
