from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class Transaction:
    action: str
    trade_date: date | str
    shares: int
    price: float
    cash_after: float
    portfolio_value_after: float


@dataclass
class Portfolio:
    initial_cash: float = 10000.0
    cash: float = field(init=False)
    shares: int = 0
    transactions: list[Transaction] = field(default_factory=list)

    def __post_init__(self):
        if self.initial_cash <= 0:
            raise ValueError("Initial cash must be greater than zero.")
        self.cash = round(float(self.initial_cash), 2)

    def value(self, current_price: float) -> float:
        self._validate_price(current_price)
        return round(self.cash + self.shares * current_price, 2)

    def profit_loss(self, current_price: float) -> float:
        return round(self.value(current_price) - self.initial_cash, 2)

    def buy(self, shares: int, current_price: float, trade_date: date | str) -> Transaction:
        self._validate_shares(shares)
        self._validate_price(current_price)
        cost = round(shares * current_price, 2)

        if cost > self.cash:
            raise ValueError("Not enough cash to buy requested shares.")

        self.cash = round(self.cash - cost, 2)
        self.shares += shares
        return self._record("BUY", trade_date, shares, current_price)

    def sell(self, shares: int, current_price: float, trade_date: date | str) -> Transaction:
        self._validate_shares(shares)
        self._validate_price(current_price)

        if shares > self.shares:
            raise ValueError("Not enough shares to sell.")

        self.cash = round(self.cash + shares * current_price, 2)
        self.shares -= shares
        return self._record("SELL", trade_date, shares, current_price)

    def hold(self, current_price: float, trade_date: date | str) -> Transaction:
        self._validate_price(current_price)
        return self._record("HOLD", trade_date, 0, current_price)

    def snapshot(self, current_price: float) -> dict:
        return {
            "cash": self.cash,
            "shares": self.shares,
            "current_price": round(float(current_price), 2),
            "portfolio_value": self.value(current_price),
            "profit_loss": self.profit_loss(current_price),
        }

    def _record(
        self,
        action: str,
        trade_date: date | str,
        shares: int,
        current_price: float,
    ) -> Transaction:
        transaction = Transaction(
            action=action,
            trade_date=trade_date,
            shares=shares,
            price=round(float(current_price), 2),
            cash_after=self.cash,
            portfolio_value_after=self.value(current_price),
        )
        self.transactions.append(transaction)
        return transaction

    @staticmethod
    def _validate_shares(shares: int) -> None:
        if not isinstance(shares, int) or shares <= 0:
            raise ValueError("Shares must be a positive integer.")

    @staticmethod
    def _validate_price(current_price: float) -> None:
        if current_price <= 0:
            raise ValueError("Current price must be greater than zero.")
