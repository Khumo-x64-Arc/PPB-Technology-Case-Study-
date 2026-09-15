"""Statement loading.

Open/Closed in practice: `StatementSource` defines the contract, each file
format is a subclass, and `SOURCE_REGISTRY` maps an extension to a class.
Supporting CSV or an API later means *adding* a subclass and one registry
entry -- no existing code is edited.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from .models import Account, Statement, Transaction, parse_timestamp


class StatementSource(ABC):
    """Reads one file and returns a normalised Statement."""

    label = "statement"

    def __init__(self, path: str | Path):
        self.path = Path(path)

    @abstractmethod
    def load(self) -> Statement:
        """Return the account plus its transactions."""

    def _statement(self, account: Account, rows: list[Transaction]) -> Statement:
        rows.sort(key=lambda t: (t.transaction_date, t.txn_id))
        return Statement(account, tuple(rows), (f"{self.label}: {self.path.name}",))


class JsonStatementSource(StatementSource):
    """Reads the bank's JSON payload (supplied with a .txt extension)."""

    label = "JSON"

    def load(self) -> Statement:
        import json

        with self.path.open(encoding="utf-8-sig") as handle:
            payload = json.load(handle)

        raw_account = payload["account"]
        account = Account(
            account_id=raw_account["accountId"],
            account_name=raw_account["accountName"],
            account_type=raw_account["accountType"],
            currency=raw_account["currency"],
            opening_balance=float(raw_account["openingBalance"]["amount"]),
            closing_balance=float(raw_account["closingBalance"]["amount"]),
            period_from=parse_timestamp(raw_account["statementPeriod"]["from"]),
            period_to=parse_timestamp(raw_account["statementPeriod"]["to"]),
            note=raw_account.get("note", ""),
        )

        rows = []
        for line in payload["statementLines"]:
            category = line["transactionCategory"]
            rows.append(
                Transaction(
                    txn_id=line["transactionId"],
                    transaction_date=parse_timestamp(line["transactionDate"]),
                    posting_date=parse_timestamp(line["postingDate"]),
                    value_date=parse_timestamp(line["valueDate"]),
                    narrative=line["narrative"],
                    category_id=int(category["transactionCategoryId"]),
                    category=category["transactionCategoryName"],
                    txn_type=line["transactionType"],
                    amount=float(line["amount"]["amount"]),
                    currency=line["amount"]["currency"],
                    running_balance=float(line["runningBalance"]["amount"]),
                    reference=line.get("transactionReference", ""),
                    disclaimer=line.get("disclaimer", "") or "",
                )
            )
        return self._statement(account, rows)


class ExcelStatementSource(StatementSource):
    """Reads the workbook's 'Account' and 'Transactions' sheets."""

    label = "Excel"
    ACCOUNT_SHEET = "Account"
    TRANSACTION_SHEET = "Transactions"

    def load(self) -> Statement:
        from openpyxl import load_workbook

        book = load_workbook(self.path, read_only=True, data_only=True)

        fields = {}
        for key, value in book[self.ACCOUNT_SHEET].iter_rows(min_row=2, values_only=True):
            if key:
                fields[str(key).strip()] = value

        account = Account(
            account_id=str(fields["Account ID"]),
            account_name=str(fields["Account Name"]),
            account_type=str(fields["Account Type"]),
            currency=str(fields["Currency"]),
            opening_balance=float(fields["Opening Balance"]),
            closing_balance=float(fields["Closing Balance"]),
            period_from=parse_timestamp(fields["Statement From"]),
            period_to=parse_timestamp(fields["Statement To"]),
            note=str(fields.get("Note", "") or ""),
        )

        sheet = book[self.TRANSACTION_SHEET]
        rows_iter = sheet.iter_rows(values_only=True)
        header = [str(cell).strip() if cell else "" for cell in next(rows_iter)]
        index = {name: position for position, name in enumerate(header)}

        def cell(row, name, default=None):
            position = index.get(name)
            if position is None or position >= len(row):
                return default
            value = row[position]
            return default if value is None else value

        rows = []
        for row in rows_iter:
            if not any(row):
                continue
            rows.append(
                Transaction(
                    txn_id=str(cell(row, "Transaction ID", "")),
                    transaction_date=parse_timestamp(cell(row, "Transaction Date")),
                    posting_date=parse_timestamp(cell(row, "Posting Date")),
                    value_date=parse_timestamp(cell(row, "Value Date")),
                    narrative=str(cell(row, "Narrative", "")),
                    category_id=int(cell(row, "Category ID", 0)),
                    category=str(cell(row, "Category", "Uncategorised")),
                    txn_type=str(cell(row, "Type", "DEBIT")),
                    amount=float(cell(row, "Amount", 0.0)),
                    currency=str(cell(row, "Currency", account.currency)),
                    running_balance=float(cell(row, "Running Balance", 0.0)),
                    reference=str(cell(row, "Reference", "")),
                    disclaimer=str(cell(row, "Disclaimer", "")),
                )
            )
        book.close()
        return self._statement(account, rows)


#: Extension -> source class. The one place to register a new format.
SOURCE_REGISTRY: dict[str, type[StatementSource]] = {
    ".json": JsonStatementSource,
    ".txt": JsonStatementSource,
    ".xlsx": ExcelStatementSource,
    ".xlsm": ExcelStatementSource,
}


def source_for(path: str | Path) -> StatementSource:
    """Pick the right reader for a file, by extension."""
    path = Path(path)
    try:
        return SOURCE_REGISTRY[path.suffix.lower()](path)
    except KeyError:
        raise ValueError(f"No reader registered for '{path.suffix}' files") from None


def load_statement(paths) -> Statement:
    """Load every given file and merge them into one statement.

    Both supplied files describe the same 30 days, so rows are de-duplicated
    on Transaction ID: reading both proves the readers agree, without
    double-counting a single cent.
    """
    account = None
    merged: dict[str, Transaction] = {}
    labels: list[str] = []

    for path in paths:
        statement = source_for(path).load()
        account = account or statement.account
        labels.extend(statement.sources)
        for txn in statement.transactions:
            merged.setdefault(txn.txn_id, txn)

    if account is None:
        raise ValueError("No statement files were supplied")

    rows = sorted(merged.values(), key=lambda t: (t.transaction_date, t.txn_id))
    return Statement(account, tuple(rows), tuple(labels))
