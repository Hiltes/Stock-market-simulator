import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from main.services.data_loader import StockDataError, load_stock_prices_with_history
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
        model_params = _model_params_from_payload(payload)

        stock_data = load_stock_prices_with_history(
            ticker,
            start_date,
            end_date,
            history_calendar_days=_history_buffer_calendar_days(model_params),
        )
        state = create_simulation_state(
            stock_data['ticker'],
            stock_data['prices'],
            initial_cash,
            model_prices=stock_data['model_prices'],
            model_history_days=stock_data['model_history_days'],
        )
        state['model_params'] = model_params
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
            'prediction_evaluation_history': state.get('prediction_evaluation_history', []),
        }
    )


def _handle_decision(request):
    state = request.session.get('simulation_state')
    if not state:
        return _error_response('Brak aktywnej symulacji.', 404, 'simulation_not_started')

    try:
        payload = _json_payload(request)
        prediction_before_action = _prediction_for_state(state, _build_ml_artifacts(state))
        perform_action(state, payload.get('action'), payload.get('shares'))
        _append_prediction_evaluation(state, prediction_before_action)
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
    response['data_stats'] = _data_stats(state)
    return response


def _build_ml_artifacts(state):
    params = state.get('model_params', {})
    try:
        model_history_days = int(state.get('model_history_days', 0))
        return build_prediction_artifacts(
            state.get('model_prices', state['prices']),
            current_step=model_history_days + int(state['current_step']),
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
        'train_rows': artifacts.get('train_rows'),
        'test_rows': artifacts.get('test_rows'),
        'warning': artifacts.get('warning'),
    }


def _data_stats(state):
    visible_prices = state['prices'][: int(state['current_step']) + 1]
    closes = [float(item['close']) for item in visible_prices]
    volumes = [int(item['volume']) for item in visible_prices]
    first_close = closes[0]
    last_close = closes[-1]
    period_return_percent = ((last_close - first_close) / first_close) * 100 if first_close else 0

    return {
        'visible_days': len(visible_prices),
        'first_date': visible_prices[0]['date'],
        'last_date': visible_prices[-1]['date'],
        'min_close': f'{min(closes):.2f}',
        'max_close': f'{max(closes):.2f}',
        'avg_close': f'{(sum(closes) / len(closes)):.2f}',
        'avg_volume': int(sum(volumes) / len(volumes)),
        'period_return_percent': round(period_return_percent, 4),
    }


def _append_prediction_evaluation(state, prediction):
    history = state.setdefault('prediction_evaluation_history', [])
    target_date = prediction.get('target_date')
    current_day = state['prices'][int(state['current_step'])]
    if not target_date or target_date != current_day['date']:
        return

    actual_close = float(current_day['close'])
    predicted_close = float(prediction['predicted_close'])
    error = actual_close - predicted_close
    actual_direction = _actual_direction(state)
    predicted_direction = prediction.get('direction', 'FLAT')

    history.append(
        {
            'based_on_date': prediction.get('based_on_date'),
            'target_date': target_date,
            'predicted_close': f'{predicted_close:.2f}',
            'actual_close': f'{actual_close:.2f}',
            'error': f'{error:.2f}',
            'absolute_error': f'{abs(error):.2f}',
            'predicted_direction': predicted_direction,
            'actual_direction': actual_direction,
            'direction_match': predicted_direction == actual_direction,
            'probability_up': prediction.get('probability_up'),
            'probability_down': prediction.get('probability_down'),
        }
    )


def _actual_direction(state):
    current_step = int(state['current_step'])
    if current_step == 0:
        return 'FLAT'

    previous_close = float(state['prices'][current_step - 1]['close'])
    current_close = float(state['prices'][current_step]['close'])
    if current_close > previous_close:
        return 'UP'
    if current_close < previous_close:
        return 'DOWN'
    return 'FLAT'


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


def _history_buffer_calendar_days(model_params):
    training_window_days = int(model_params.get('training_window_days', DEFAULT_TRAINING_WINDOW_DAYS))
    lookback_days = int(model_params.get('lookback_days', DEFAULT_LOOKBACK_DAYS))
    return max(45, training_window_days * 2 + lookback_days * 4)


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
