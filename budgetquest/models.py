"""Domain models.

Every data source normalises into these types, so the analytics engine and
the UI never need to know whether a row came from Excel or from JSON.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

ISO_FORMAT = "%Y-%m-%dT%H:%M:%S.%f%z"

CREDIT = "CREDIT"
DEBIT = "DEBIT"


def parse_timestamp(value) -> datetime:
    """Parse '2026-08-01T08:05:00.000+0200'. Accepts datetimes untouched."""
    if isinstance(value, datetime):
        return value
    return datetime.strptime(str(value).strip(), ISO_FORMAT)


@dataclass(frozen=True)
class Transaction:
    txn_id: str
    transaction_date: datetime
    posting_date: datetime
    value_date: datetime
    narrative: str
    category_id: int
    category: str
    txn_type: str
    amount: float          # signed: negative for DEBIT
    currency: str
    running_balance: float
    reference: str = ""
    disclaimer: str = ""

    # -- derived, rule-based properties -------------------------------------
    @property
    def is_debit(self) -> bool:
        return self.txn_type.upper() == DEBIT

    @property
    def is_credit(self) -> bool:
        return self.txn_type.upper() == CREDIT

    @property
    def outflow(self) -> float:
        """Money leaving the account, always positive."""
        return abs(self.amount) if self.is_debit else 0.0

    @property
    def inflow(self) -> float:
        return abs(self.amount) if self.is_credit else 0.0

    @property
    def day(self) -> date:
        return self.transaction_date.date()

    @property
    def hour(self) -> int:
        return self.transaction_date.hour

    @property
    def settlement_hours(self) -> float:
        """Hours between the transaction and it posting to the account."""
        delta = self.posting_date - self.transaction_date
        return delta.total_seconds() / 3600.0


@dataclass(frozen=True)
class Account:
    account_id: str
    account_name: str
    account_type: str
    currency: str
    opening_balance: float
    closing_balance: float
    period_from: datetime
    period_to: datetime
    note: str = ""

    @property
    def days(self) -> int:
        return (self.period_to.date() - self.period_from.date()).days + 1


@dataclass(frozen=True)
class Statement:
    account: Account
    transactions: tuple[Transaction, ...]
    sources: tuple[str, ...] = field(default_factory=tuple)

    def __len__(self) -> int:
        return len(self.transactions)
