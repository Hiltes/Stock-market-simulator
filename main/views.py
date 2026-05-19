import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from main.services.data_loader import StockDataError, load_stock_prices
from main.services.simulator_engine import (
    SimulationError,
    create_simulation_state,
    perform_action,
    serialize_state,
)


def home(request):
    return render(request, 'main/home.html')


@require_POST
def api_start_simulation(request):
    try:
        payload = _json_payload(request)
        ticker = payload.get('ticker')
        start_date = payload.get('start_date')
        end_date = payload.get('end_date')
        initial_cash = payload.get('initial_cash', '10000')

        prices = load_stock_prices(ticker, start_date, end_date)
        state = create_simulation_state(ticker.strip().upper(), prices, initial_cash)
        request.session['simulation_state'] = state
        request.session.modified = True

        return JsonResponse(_state_response(state))
    except (StockDataError, SimulationError, ValueError) as exc:
        return _error_response(str(exc), status=400)


@require_POST
def api_action(request):
    state = request.session.get('simulation_state')
    if not state:
        return _error_response('Brak aktywnej symulacji.', status=404)

    try:
        payload = _json_payload(request)
        perform_action(state, payload.get('action'), payload.get('shares'))
        request.session['simulation_state'] = state
        request.session.modified = True

        response = _state_response(state)
        response['last_transaction'] = state['history'][-1] if state['history'] else None
        return JsonResponse(response)
    except (SimulationError, ValueError) as exc:
        return _error_response(str(exc), status=400)


@require_GET
def api_history(request):
    state = request.session.get('simulation_state')
    if not state:
        return _error_response('Brak aktywnej symulacji.', status=404)

    return JsonResponse(
        {
            'history': state.get('history', []),
            'portfolio_history': state.get('portfolio_history', []),
        }
    )


def _state_response(state):
    response = serialize_state(state)
    response['prediction'] = _baseline_prediction(state)
    return response


def _baseline_prediction(state):
    current_step = int(state['current_step'])
    prices = state['prices']
    current_close = float(prices[current_step]['close'])

    if current_step == 0:
        predicted_close = current_close
    else:
        previous_close = float(prices[current_step - 1]['close'])
        predicted_close = current_close + (current_close - previous_close)

    direction = 'UP' if predicted_close > current_close else 'DOWN' if predicted_close < current_close else 'FLAT'
    return {
        'model': 'model bazowy momentum',
        'predicted_close': f'{predicted_close:.2f}',
        'direction': direction,
        'confidence': 0.5,
    }


def _json_payload(request):
    try:
        return json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError as exc:
        raise ValueError('Niepoprawny JSON.') from exc


def _error_response(message, status):
    return JsonResponse({'error': message}, status=status)
