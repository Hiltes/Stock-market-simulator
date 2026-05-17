from datetime import date

import pandas as pd
from django.test import SimpleTestCase

from main.services.data_loader import normalize_ticker, stock_prices_from_frame
from main.services.simulator_engine import Portfolio


class PortfolioTests(SimpleTestCase):
    def test_buy_sell_and_hold_update_portfolio_state(self):
        portfolio = Portfolio(initial_cash=1000)

        buy = portfolio.buy(2, 100.0, date(2024, 1, 2))
        hold = portfolio.hold(120.0, date(2024, 1, 3))
        sell = portfolio.sell(1, 150.0, date(2024, 1, 4))

        self.assertEqual(buy.action, "BUY")
        self.assertEqual(hold.action, "HOLD")
        self.assertEqual(sell.action, "SELL")
        self.assertEqual(portfolio.cash, 950.0)
        self.assertEqual(portfolio.shares, 1)
        self.assertEqual(portfolio.value(150.0), 1100.0)
        self.assertEqual(portfolio.profit_loss(150.0), 100.0)
        self.assertEqual(len(portfolio.transactions), 3)

    def test_buy_rejects_when_cash_is_too_low(self):
        portfolio = Portfolio(initial_cash=100)

        with self.assertRaisesMessage(ValueError, "Not enough cash"):
            portfolio.buy(2, 100.0, "2024-01-02")

    def test_sell_rejects_when_shares_are_too_low(self):
        portfolio = Portfolio(initial_cash=100)

        with self.assertRaisesMessage(ValueError, "Not enough shares"):
            portfolio.sell(1, 100.0, "2024-01-02")


class DataLoaderTests(SimpleTestCase):
    def test_normalize_ticker(self):
        self.assertEqual(normalize_ticker(" aapl "), "AAPL")

    def test_stock_prices_from_frame_maps_required_columns(self):
        frame = pd.DataFrame(
            [
                {
                    "Date": "2024-01-02",
                    "Open": 100.123,
                    "High": 110.125,
                    "Low": 95.111,
                    "Close": 105.555,
                    "Volume": 12345,
                }
            ]
        ).set_index("Date")

        prices = stock_prices_from_frame(frame)

        self.assertEqual(len(prices), 1)
        self.assertEqual(prices[0].close, 105.56)
        self.assertEqual(prices[0].volume, 12345)
