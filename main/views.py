import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from main.services.data_loader import StockDataError, load_stock_prices
from main.services.ml_model import (
    DEFAULT_LOOKBACK_DAYS,
    DEFAULT_TRAINING_WINDOW_DAYS,
    ModelTrainingError,
    build_prediction_artifacts,
)
from main.services.simulator_engine import (
    SimulationError,
    create_simulation_state,
    perform_action,
    serialize_state,
)


def home(request):
    return render(
        request,
        'main/home.html',
        {
            'default_training_window_days': DEFAULT_TRAINING_WINDOW_DAYS,
            'default_lookback_days': DEFAULT_LOOKBACK_DAYS,
        },
    )


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
        state['model_params'] = _model_params_from_payload(payload)
        _save_simulation_state(request, state)

        return JsonResponse(_state_response(state))
    except (StockDataError, SimulationError, ModelTrainingError) as exc:
        return _error_response(str(exc), getattr(exc, 'status', 400), getattr(exc, 'code', 'bad_request'))
    except ValueError as exc:
        return _error_response(str(exc), 400, 'invalid_request')


@require_POST
def api_decision(request):
    return _handle_decision(request)


@require_POST
def api_action(request):
    return _handle_decision(request)


@require_GET
def api_history(request):
    state = request.session.get('simulation_state')
    if not state:
        return _error_response('Brak aktywnej symulacji.', 404, 'simulation_not_started')

    return JsonResponse(
        {
            'history': state.get('history', []),
            'transaction_history': state.get('history', []),
            'portfolio_history': state.get('portfolio_history', []),
        }
    )


def _handle_decision(request):
    state = request.session.get('simulation_state')
    if not state:
        return _error_response('Brak aktywnej symulacji.', 404, 'simulation_not_started')

    try:
        payload = _json_payload(request)
        perform_action(state, payload.get('action'), payload.get('shares'))
        _save_simulation_state(request, state)

        response = _state_response(state)
        response['last_transaction'] = state['history'][-1] if state['history'] else None
        return JsonResponse(response)
    except SimulationError as exc:
        return _error_response(str(exc), getattr(exc, 'status', 400), getattr(exc, 'code', 'bad_request'))
    except ValueError as exc:
        return _error_response(str(exc), 400, 'invalid_request')


def _save_simulation_state(request, state):
    request.session['simulation_state'] = state
    request.session.modified = True


def _state_response(state):
    artifacts = _build_ml_artifacts(state)
    response = serialize_state(state)
    response['prediction'] = _prediction_for_state(state, artifacts)
    response['model_metrics'] = _model_metrics(artifacts)
    response['model_params'] = state.get('model_params', {})
    return response


def _build_ml_artifacts(state):
    params = state.get('model_params', {})
    try:
        return build_prediction_artifacts(
            state['prices'],
            current_step=int(state['current_step']),
            training_window_days=int(params.get('training_window_days', DEFAULT_TRAINING_WINDOW_DAYS)),
            lookback_days=int(params.get('lookback_days', DEFAULT_LOOKBACK_DAYS)),
        )
    except ModelTrainingError as exc:
        return {
            'model_name': 'Model bazowy',
            'metrics': None,
            'current_prediction': None,
            'model_params': params,
            'warning': str(exc),
        }


def _prediction_for_state(state, artifacts):
    prediction = (artifacts or {}).get('current_prediction')
    if prediction:
        return prediction
    return _baseline_prediction(state)


def _model_metrics(artifacts):
    artifacts = artifacts or {}
    return {
        'model_name': artifacts.get('model_name', 'Model bazowy'),
        'metrics': artifacts.get('metrics'),
        'warning': artifacts.get('warning'),
    }


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
    change = predicted_close - current_close
    change_percent = (change / current_close) * 100 if current_close else 0
    target_date = prices[current_step + 1]['date'] if current_step + 1 < len(prices) else None
    return {
        'model': 'model bazowy momentum',
        'predicted_close': f'{predicted_close:.2f}',
        'direction': direction,
        'confidence': 0.5,
        'probability_up': 0.5,
        'probability_down': 0.5,
        'change': f'{change:.2f}',
        'change_percent': round(change_percent, 4),
        'based_on_date': prices[current_step]['date'],
        'target_date': target_date,
    }


def _model_params_from_payload(payload):
    return {
        'training_window_days': _positive_int(payload.get('training_window_days', DEFAULT_TRAINING_WINDOW_DAYS), 'training_window_days', minimum=10),
        'lookback_days': _positive_int(payload.get('lookback_days', DEFAULT_LOOKBACK_DAYS), 'lookback_days', minimum=2),
    }


def _positive_int(value, field_name, minimum=1):
    try:
        parsed_value = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'Pole {field_name} musi byc liczba calkowita.') from exc

    if parsed_value < minimum:
        raise ValueError(f'Pole {field_name} musi byc nie mniejsze niz {minimum}.')

    return parsed_value


def _json_payload(request):
    try:
        return json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError as exc:
        raise ValueError('Niepoprawny JSON.') from exc


def _error_response(message, status, code='bad_request'):
    return JsonResponse({'error': message, 'error_code': code}, status=status)
