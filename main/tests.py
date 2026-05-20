from copy import deepcopy
from datetime import date, timedelta
from unittest.mock import patch

from django.test import Client, SimpleTestCase, override_settings

from main.services.data_loader import StockDataError
from main.services.ml_model import build_prediction_artifacts
from main.services.preprocessing import FEATURE_COLUMNS, build_feature_columns, build_feature_frame
from main.services.simulator_engine import (
    SimulationError,
    create_simulation_state,
    perform_action,
    portfolio_snapshot,
    serialize_state,
    simulation_summary,
)


SAMPLE_PRICES = [
    {'date': '2024-01-02', 'open': '100.00', 'high': '110.00', 'low': '99.00', 'close': '100.00', 'volume': 1000},
    {'date': '2024-01-03', 'open': '101.00', 'high': '112.00', 'low': '100.00', 'close': '110.00', 'volume': 1200},
    {'date': '2024-01-04', 'open': '109.00', 'high': '115.00', 'low': '105.00', 'close': '105.00', 'volume': 900},
]

ML_ARTIFACTS = {
    'model_name': 'Random Forest',
    'metrics': {
        'regression': {'mae': 1.0, 'rmse': 1.5, 'r2': 0.7},
        'classification': {'accuracy': 0.8, 'precision': 0.75, 'recall': 0.8, 'f1': 0.77},
    },
    'model_params': {
        'training_window_days': 45,
        'lookback_days': 4,
        'train_ratio': 0.75,
        'n_estimators': 80,
    },
    'current_prediction': {
        'model': 'Random Forest',
        'predicted_close': '111.00',
        'direction': 'UP',
        'confidence': 0.8,
        'probability_up': 0.8,
        'probability_down': 0.2,
        'change': '1.00',
        'change_percent': 0.91,
        'based_on_date': '2024-01-02',
        'target_date': '2024-01-03',
    },
    'warning': None,
}


def synthetic_prices(days=40):
    prices = []
    start = date(2024, 2, 1)
    for index in range(days):
        current_date = start + timedelta(days=index)
        close = 100 + index * 1.5
        prices.append(
            {
                'date': current_date.isoformat(),
                'open': f'{close - 0.50:.2f}',
                'high': f'{close + 1.50:.2f}',
                'low': f'{close - 1.25:.2f}',
                'close': f'{close:.2f}',
                'volume': 1000 + index * 10,
            }
        )
    return prices


class PreprocessingTests(SimpleTestCase):
    def test_feature_frame_contains_time_series_features_and_targets(self):
        feature_columns = build_feature_columns(4)
        frame = build_feature_frame(synthetic_prices(), lookback_days=4)

        self.assertGreater(len(frame), 0)
        for column in feature_columns + ['target_close', 'target_direction']:
            self.assertIn(column, frame.columns)
        self.assertTrue(set(frame['target_direction'].unique()).issubset({0, 1}))

    def test_default_feature_columns_constant_matches_default_builder(self):
        self.assertEqual(FEATURE_COLUMNS, build_feature_columns())


class MlModelTests(SimpleTestCase):
    def test_prediction_artifacts_contain_metrics_and_current_prediction(self):
        prices = synthetic_prices(70)

        artifacts = build_prediction_artifacts(
            prices,
            current_step=45,
            training_window_days=30,
            lookback_days=4,
            n_estimators=10,
        )

        self.assertEqual(artifacts['model_name'], 'Random Forest')
        self.assertIn('regression', artifacts['metrics'])
        self.assertIn('classification', artifacts['metrics'])
        self.assertEqual(artifacts['current_prediction']['target_date'], prices[46]['date'])
        self.assertEqual(artifacts['model_params']['training_window_days'], 30)
        self.assertEqual(artifacts['model_params']['lookback_days'], 4)

    def test_walk_forward_prediction_ignores_future_rows_after_current_step(self):
        base_prices = synthetic_prices(80)
        mutated_prices = deepcopy(base_prices)
        for index in range(50, len(mutated_prices)):
            mutated_prices[index]['open'] = '999.00'
            mutated_prices[index]['high'] = '1005.00'
            mutated_prices[index]['low'] = '995.00'
            mutated_prices[index]['close'] = '1000.00'
            mutated_prices[index]['volume'] = 999999

        base_artifacts = build_prediction_artifacts(
            base_prices,
            current_step=40,
            training_window_days=30,
            lookback_days=4,
            n_estimators=10,
        )
        mutated_artifacts = build_prediction_artifacts(
            mutated_prices,
            current_step=40,
            training_window_days=30,
            lookback_days=4,
            n_estimators=10,
        )

        self.assertEqual(base_artifacts['current_prediction'], mutated_artifacts['current_prediction'])
        self.assertEqual(base_artifacts['metrics'], mutated_artifacts['metrics'])


class SimulatorEngineTests(SimpleTestCase):
    def test_buy_updates_cash_shares_and_portfolio_value(self):
        state = create_simulation_state('AAPL', SAMPLE_PRICES, '1000.00')

        perform_action(state, 'BUY', 3)

        self.assertEqual(state['cash'], '700.00')
        self.assertEqual(state['shares'], 3)
        self.assertEqual(state['history'][0]['action'], 'BUY')
        self.assertEqual(portfolio_snapshot(state)['portfolio_value'], '1030.00')

    def test_sell_requires_owned_shares(self):
        state = create_simulation_state('AAPL', SAMPLE_PRICES, '1000.00')

        with self.assertRaises(SimulationError) as context:
            perform_action(state, 'SELL', 1)

        self.assertEqual(context.exception.code, 'insufficient_shares')

    def test_hold_advances_without_transaction_cost(self):
        state = create_simulation_state('AAPL', SAMPLE_PRICES, '1000.00')

        perform_action(state, 'HOLD')

        self.assertEqual(state['cash'], '1000.00')
        self.assertEqual(state['shares'], 0)
        self.assertEqual(state['current_step'], 1)
        self.assertEqual(state['history'][0]['action'], 'HOLD')

    def test_finished_state_blocks_additional_actions(self):
        state = create_simulation_state('AAPL', SAMPLE_PRICES, '1000.00')

        perform_action(state, 'HOLD')
        perform_action(state, 'HOLD')

        self.assertEqual(state['status'], 'finished')
        with self.assertRaises(SimulationError) as context:
            perform_action(state, 'HOLD')

        self.assertEqual(context.exception.code, 'simulation_finished')
        self.assertEqual(context.exception.status, 409)

    def test_serialize_state_exposes_only_current_snapshot(self):
        state = create_simulation_state('AAPL', SAMPLE_PRICES, '1000.00')

        serialized = serialize_state(state)

        self.assertEqual(serialized['total_days'], 3)
        self.assertEqual(serialized['current_day']['date'], '2024-01-02')
        self.assertEqual(serialized['ohlcv']['close'], '100.00')
        self.assertEqual(serialized['transaction_history'], [])
        self.assertNotIn('prices', serialized)

    def test_summary_compares_result_with_buy_and_hold(self):
        state = create_simulation_state('AAPL', SAMPLE_PRICES, '1000.00')

        perform_action(state, 'BUY', 2)
        perform_action(state, 'HOLD')

        summary = simulation_summary(state)

        self.assertEqual(summary['transaction_count'], 2)
        self.assertIn('buy_and_hold_value', summary)
        self.assertIn('difference_vs_buy_and_hold', summary)


@override_settings(SESSION_ENGINE='django.contrib.sessions.backends.signed_cookies')
class SimulationApiTests(SimpleTestCase):
    def setUp(self):
        self.client = Client()

    @patch('main.views.build_prediction_artifacts', return_value=ML_ARTIFACTS)
    @patch('main.views.load_stock_prices', return_value=SAMPLE_PRICES)
    def test_start_simulation_returns_first_day_state_and_model_params(self, _load_stock_prices, build_prediction_artifacts_mock):
        response = self.client.post(
            '/api/start',
            data={
                'ticker': 'AAPL',
                'start_date': '2024-01-01',
                'end_date': '2024-01-10',
                'initial_cash': '1000',
                'training_window_days': 45,
                'lookback_days': 4,
            },
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['ticker'], 'AAPL')
        self.assertEqual(payload['total_days'], 3)
        self.assertEqual(payload['current_day']['date'], '2024-01-02')
        self.assertEqual(payload['ohlcv']['close'], '100.00')
        self.assertEqual(payload['cash'], '1000.00')
        self.assertEqual(payload['shares'], 0)
        self.assertEqual(payload['transaction_history'], [])
        self.assertEqual(payload['prediction']['model'], 'Random Forest')
        self.assertEqual(payload['model_params']['training_window_days'], 45)
        self.assertEqual(payload['model_params']['lookback_days'], 4)
        self.assertNotIn('prices', payload)
        build_prediction_artifacts_mock.assert_called_once()
        self.assertEqual(build_prediction_artifacts_mock.call_args.kwargs['current_step'], 0)
        self.assertEqual(build_prediction_artifacts_mock.call_args.kwargs['training_window_days'], 45)
        self.assertEqual(build_prediction_artifacts_mock.call_args.kwargs['lookback_days'], 4)

    @patch('main.views.build_prediction_artifacts', return_value=ML_ARTIFACTS)
    @patch('main.views.load_stock_prices', return_value=SAMPLE_PRICES)
    def test_decision_updates_session_and_advances_by_one_day(self, _load_stock_prices, _build_prediction_artifacts):
        self.client.post(
            '/api/start',
            data={
                'ticker': 'AAPL',
                'start_date': '2024-01-01',
                'end_date': '2024-01-10',
                'initial_cash': '1000',
                'training_window_days': 45,
                'lookback_days': 4,
            },
            content_type='application/json',
        )

        response = self.client.post(
            '/api/decision',
            data={'action': 'BUY', 'shares': 2},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['current_day']['date'], '2024-01-03')
        self.assertEqual(payload['cash'], '800.00')
        self.assertEqual(payload['shares'], 2)
        self.assertEqual(payload['portfolio_value'], '1020.00')
        self.assertEqual(payload['profit_loss'], '20.00')
        self.assertEqual(len(payload['transaction_history']), 1)
        self.assertEqual(payload['last_transaction']['action'], 'BUY')
        self.assertEqual(payload['model_params']['training_window_days'], 45)
        self.assertNotIn('prices', payload)

    @patch('main.views.load_stock_prices')
    def test_start_simulation_returns_readable_error_for_invalid_ticker(self, load_stock_prices):
        load_stock_prices.side_effect = StockDataError('Nieobslugiwany ticker.', code='invalid_ticker')

        response = self.client.post(
            '/api/start',
            data={
                'ticker': 'BAD',
                'start_date': '2024-01-01',
                'end_date': '2024-01-10',
                'initial_cash': '1000',
                'training_window_days': 45,
                'lookback_days': 4,
            },
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {'error': 'Nieobslugiwany ticker.', 'error_code': 'invalid_ticker'},
        )

    @patch('main.views.build_prediction_artifacts', return_value=ML_ARTIFACTS)
    @patch('main.views.load_stock_prices', return_value=SAMPLE_PRICES)
    def test_decision_returns_readable_error_for_insufficient_cash(self, _load_stock_prices, _build_prediction_artifacts):
        self.client.post(
            '/api/start',
            data={
                'ticker': 'AAPL',
                'start_date': '2024-01-01',
                'end_date': '2024-01-10',
                'initial_cash': '1000',
                'training_window_days': 45,
                'lookback_days': 4,
            },
            content_type='application/json',
        )

        response = self.client.post(
            '/api/decision',
            data={'action': 'BUY', 'shares': 20},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error_code'], 'insufficient_cash')

    @patch('main.views.build_prediction_artifacts', return_value=ML_ARTIFACTS)
    @patch('main.views.load_stock_prices', return_value=SAMPLE_PRICES)
    def test_decision_returns_error_when_simulation_is_finished(self, _load_stock_prices, _build_prediction_artifacts):
        self.client.post(
            '/api/start',
            data={
                'ticker': 'AAPL',
                'start_date': '2024-01-01',
                'end_date': '2024-01-10',
                'initial_cash': '1000',
                'training_window_days': 45,
                'lookback_days': 4,
            },
            content_type='application/json',
        )

        self.client.post('/api/decision', data={'action': 'HOLD', 'shares': 0}, content_type='application/json')
        self.client.post('/api/decision', data={'action': 'HOLD', 'shares': 0}, content_type='application/json')
        response = self.client.post(
            '/api/decision',
            data={'action': 'HOLD', 'shares': 0},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['error_code'], 'simulation_finished')

    def test_decision_requires_active_simulation(self):
        response = self.client.post(
            '/api/decision',
            data={'action': 'HOLD', 'shares': 0},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['error_code'], 'simulation_not_started')

    @patch('main.views.load_stock_prices', return_value=SAMPLE_PRICES)
    def test_start_simulation_validates_model_params(self, _load_stock_prices):
        response = self.client.post(
            '/api/start',
            data={
                'ticker': 'AAPL',
                'start_date': '2024-01-01',
                'end_date': '2024-01-10',
                'initial_cash': '1000',
                'training_window_days': 5,
                'lookback_days': 1,
            },
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error_code'], 'invalid_request')
