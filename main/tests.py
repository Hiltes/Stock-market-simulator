from datetime import date, timedelta
from unittest.mock import patch

from django.test import Client, SimpleTestCase, override_settings

from main.services.ml_model import build_prediction_artifacts
from main.services.preprocessing import FEATURE_COLUMNS, build_feature_frame
from main.services.simulator_engine import (
    SimulationError,
    create_simulation_state,
    perform_action,
    portfolio_snapshot,
)


SAMPLE_PRICES = [
    {'date': '2024-01-02', 'open': '100.00', 'high': '110.00', 'low': '99.00', 'close': '100.00', 'volume': 1000},
    {'date': '2024-01-03', 'open': '101.00', 'high': '112.00', 'low': '100.00', 'close': '110.00', 'volume': 1200},
    {'date': '2024-01-04', 'open': '109.00', 'high': '115.00', 'low': '105.00', 'close': '105.00', 'volume': 900},
]


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
        frame = build_feature_frame(synthetic_prices())

        self.assertGreater(len(frame), 0)
        for column in FEATURE_COLUMNS + ['target_close', 'target_direction']:
            self.assertIn(column, frame.columns)
        self.assertTrue(set(frame['target_direction'].unique()).issubset({0, 1}))


class MlModelTests(SimpleTestCase):
    def test_prediction_artifacts_contain_metrics_and_daily_predictions(self):
        artifacts = build_prediction_artifacts(synthetic_prices(60), n_estimators=10)

        self.assertEqual(artifacts['model_name'], 'Random Forest')
        self.assertIn('regression', artifacts['metrics'])
        self.assertIn('classification', artifacts['metrics'])
        self.assertGreater(len(artifacts['predictions_by_date']), 0)


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

        with self.assertRaises(SimulationError):
            perform_action(state, 'SELL', 1)

    def test_hold_advances_without_transaction_cost(self):
        state = create_simulation_state('AAPL', SAMPLE_PRICES, '1000.00')

        perform_action(state, 'HOLD')

        self.assertEqual(state['cash'], '1000.00')
        self.assertEqual(state['shares'], 0)
        self.assertEqual(state['current_step'], 1)
        self.assertEqual(state['history'][0]['action'], 'HOLD')

    def test_simulation_finishes_on_last_available_day(self):
        state = create_simulation_state('AAPL', SAMPLE_PRICES, '1000.00')

        perform_action(state, 'HOLD')
        perform_action(state, 'HOLD')

        self.assertEqual(state['status'], 'finished')


@override_settings(SESSION_ENGINE='django.contrib.sessions.backends.signed_cookies')
class SimulationApiTests(SimpleTestCase):
    def setUp(self):
        self.client = Client()

    @patch('main.views.load_stock_prices')
    def test_start_simulation_returns_current_day_and_portfolio(self, load_stock_prices):
        load_stock_prices.return_value = SAMPLE_PRICES

        response = self.client.post(
            '/api/start/',
            data={
                'ticker': 'AAPL',
                'start_date': '2024-01-01',
                'end_date': '2024-01-10',
                'initial_cash': '1000',
            },
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['ticker'], 'AAPL')
        self.assertEqual(payload['current_day']['date'], '2024-01-02')
        self.assertEqual(payload['portfolio']['cash'], '1000.00')
        self.assertEqual(payload['prediction']['model'], 'model bazowy momentum')
        self.assertIn('model_metrics', payload)

    @patch('main.views.load_stock_prices')
    def test_action_updates_session_state(self, load_stock_prices):
        load_stock_prices.return_value = SAMPLE_PRICES
        self.client.post(
            '/api/start/',
            data={
                'ticker': 'AAPL',
                'start_date': '2024-01-01',
                'end_date': '2024-01-10',
                'initial_cash': '1000',
            },
            content_type='application/json',
        )

        response = self.client.post(
            '/api/action/',
            data={'action': 'BUY', 'shares': 2},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['portfolio']['shares'], 2)
        self.assertEqual(payload['last_transaction']['action'], 'BUY')
