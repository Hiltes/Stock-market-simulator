from django.test import SimpleTestCase

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
