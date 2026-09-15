"""The rule book.

Everything in this file is plain data or a small pure function. There is no
machine learning and no statistical model anywhere in BudgetQuest -- every
number the app shows can be traced back to a threshold or an if/then written
here, in English, next to the rule it drives.

This module is also the Open/Closed seam. New budgets, badges, challenges,
fraud checks and rewards tips are *appended* to the lists below; the engine
and the UI loop over whatever they find and never need editing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .formatting import rand

# ---------------------------------------------------------------------------
# Core thresholds
# ---------------------------------------------------------------------------

SALARY_NARRATIVE = "SALARY DEPOSIT - EMPLOYER PAYROLL"
SAVINGS_NARRATIVE = "TRANSFER TO SAVINGS POCKET"

SAVINGS_GOAL_RATE = 0.15        # target: save 15% of every salary
SETTLEMENT_SLA_HOURS = 24.0     # a posting must reflect within 24 hours
FRAUD_ESCALATION_HITS = 2       # 2+ triggered checks -> Fraud department
NIGHT_START_HOUR, NIGHT_END_HOUR = 0, 5
LARGE_PURCHASE_RATE = 0.05      # a single card buy above 5% of salary is "large"

INCOME_CATEGORIES = ("Income / Salary",)
REFUND_CATEGORIES = ("Refund / Reversal",)

# Scheduled money the customer has effectively already promised away. Used by
# the 75% balance notification to say what is still due before month end.
COMMITMENT_CATEGORIES = ("Fixed Commitments", "Debit Order", "Subscriptions")
COMMITMENT_NARRATIVES = ("TRANSFER TO BENEFICIARY",)


#: Narrative keywords used to spot qualifying Standard Bank products.
HOME_LOAN_KEYWORDS = ("HOME LOAN",)
VEHICLE_FINANCE_KEYWORDS = ("VEHICLE FINANCE",)
SB_INSURANCE_KEYWORDS = ("LIFE INSURANCE", "SHORT-TERM INSURANCE")
DIGITAL_PAYMENT_KEYWORDS = ("TRANSFER TO BENEFICIARY", "TRANSFER TO SAVINGS",
                            "IMMEDIATE PAYMENT")


def is_commitment(txn) -> bool:
    return txn.is_debit and (
        txn.category in COMMITMENT_CATEGORIES
        or any(word in txn.narrative.upper() for word in COMMITMENT_NARRATIVES))

# Spending budget per category, as a share of monthly salary.
CATEGORY_BUDGETS: dict[str, float] = {
    "Fixed Commitments": 0.30,
    "Debit Order": 0.12,
    "Groceries": 0.15,
    "Transport": 0.10,
    "Transfers": 0.10,
    "Discretionary Spending": 0.10,
    "Online Purchases": 0.05,
    "Cash Withdrawal": 0.05,
    "Once-off Large Purchase": 0.05,
    "Subscriptions": 0.03,
    "Bank Fees": 0.01,
    "Uncategorised / Unusual": 0.00,
}

# Blue-family palette with a few accents, so the pie stays on-theme.
CATEGORY_COLOURS: dict[str, str] = {
    "Fixed Commitments": "#0A47AC",
    "Debit Order": "#1565D8",
    "Groceries": "#2E8BE6",
    "Transport": "#23A7C4",
    "Transfers": "#17B0A0",
    "Subscriptions": "#6C63E0",
    "Online Purchases": "#9B6DE8",
    "Discretionary Spending": "#E5A400",
    "Cash Withdrawal": "#4A9BFF",
    "Once-off Large Purchase": "#0F7B8A",
    "Bank Fees": "#D64545",
    "Uncategorised / Unusual": "#C2185B",
    "Income / Salary": "#1E9E6A",
    "Refund / Reversal": "#39B87F",
}
FALLBACK_COLOURS = ("#0F5BD7", "#4A9BFF", "#23A7C4", "#6C63E0", "#9B6DE8")


def colour_for(category: str) -> str:
    """Never fails: an unknown category still gets a stable colour."""
    if category in CATEGORY_COLOURS:
        return CATEGORY_COLOURS[category]
    return FALLBACK_COLOURS[hash(category) % len(FALLBACK_COLOURS)]


def budget_for(category: str, income: float) -> float:
    """Rand budget for a category. Unlisted categories get 5% by default."""
    return income * CATEGORY_BUDGETS.get(category, 0.05)


def taper(value: float, good: float, bad: float) -> float:
    """Score helper: 1.0 at or below `good`, 0.0 at or above `bad`, linear between."""
    if value <= good:
        return 1.0
    if value >= bad:
        return 0.0
    return (bad - value) / (bad - good)


# ---------------------------------------------------------------------------
# Merchant / service recognition
# ---------------------------------------------------------------------------

def merchant_of(narrative: str) -> str:
    """Rule: the merchant or service is the text after the last ' - '.

    'CARD PURCHASE - WOOLWORTHS'  -> 'WOOLWORTHS'
    'ATM CASH WITHDRAWAL'         -> 'ATM CASH WITHDRAWAL'
    """
    parts = [part.strip() for part in narrative.split(" - ") if part.strip()]
    return parts[-1] if len(parts) > 1 else narrative.strip()


# ---------------------------------------------------------------------------
# Fraud / security checks (each takes a Transaction and the statement income)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FraudRule:
    code: str
    title: str
    reason: str
    check: Callable[..., bool]


FRAUD_RULES: tuple[FraudRule, ...] = (
    FraudRule(
        "R1", "Out-of-hours purchase",
        "Card used between midnight and 05:00, outside this customer's pattern",
        lambda txn, income: txn.is_debit
        and NIGHT_START_HOUR <= txn.hour < NIGHT_END_HOUR
        and "PURCHASE" in txn.narrative.upper(),
    ),
    FraudRule(
        "R2", "Unusual category",
        "Posted to category 199 (Uncategorised / Unusual) rather than a known one",
        lambda txn, income: txn.category_id == 199,
    ),
    FraudRule(
        "R3", "High-risk merchant type",
        "Narrative matches a merchant type with elevated chargeback risk",
        lambda txn, income: any(
            word in txn.narrative.upper()
            for word in ("GAMING", "CRYPTO", "UNRECOGNISED")
        ),
    ),
    FraudRule(
        "R4", "Cross-border exposure",
        "International merchant or a foreign-currency conversion at point of sale",
        lambda txn, income: "INTERNATIONAL" in txn.narrative.upper()
        or "FOREIGN-CURRENCY" in (txn.disclaimer or "").upper(),
    ),
    FraudRule(
        "R5", "Large single card purchase",
        f"One card purchase above {LARGE_PURCHASE_RATE:.0%} of monthly salary",
        lambda txn, income: txn.is_debit
        and "PURCHASE" in txn.narrative.upper()
        and txn.outflow > income * LARGE_PURCHASE_RATE,
    ),
    FraudRule(
        "R6", "Pushed the account into overdraft",
        "A debit of R500 or more took the running balance below zero",
        lambda txn, income: txn.is_debit
        and txn.outflow >= 500
        and txn.running_balance < 0,
    ),
)


# ---------------------------------------------------------------------------
# Money Health Score: five components, 100 points, every one explainable
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ScoreRule:
    name: str
    max_points: float
    rule_text: str
    score: Callable[..., float]   # snapshot -> 0.0 to 1.0


SCORE_RULES: tuple[ScoreRule, ...] = (
    ScoreRule(
        "Savings rate", 25,
        "Full marks for moving 15% of salary into savings. Nothing saved, no points.",
        lambda s: min(1.0, s.savings_rate / SAVINGS_GOAL_RATE) if s.income else 0.0,
    ),
    ScoreRule(
        "Closing balance", 20,
        "Full marks for ending the month positive. Overdrawn scores zero.",
        lambda s: 1.0 if s.closing_balance >= 0 else 0.0,
    ),
    ScoreRule(
        "Discretionary spending", 15,
        "Full marks at or below 10% of salary on eating out, coffee and nights out.",
        lambda s: taper(s.discretionary_rate, 0.10, 0.25),
    ),
    ScoreRule(
        "Fixed commitments", 15,
        "Full marks at or below 40% of salary on loans, debit orders and insurance.",
        lambda s: taper(s.commitment_rate, 0.40, 0.60),
    ),
    ScoreRule(
        "Bank fees", 10,
        "Full marks under R100 of fees. Zero at R400 and above.",
        lambda s: taper(s.bank_fees, 100.0, 400.0),
    ),
    ScoreRule(
        "Unflagged spending", 15,
        "Full marks when nothing lands in the unusual category. Zero at 5% of salary.",
        lambda s: taper(s.unusual_rate, 0.0, 0.05),
    ),
)

#: Money health level. Distinct from the UCount tiering levels in rewards.py:
#: this one scores behaviour, that one scores banking relationship.
HEALTH_LEVELS: tuple[tuple[int, str], ...] = (
    (90, "Diamond"),
    (75, "Platinum"),
    (55, "Gold"),
    (35, "Silver"),
    (0, "Blue"),
)


def health_level_for(score: float) -> tuple[str, int | None]:
    """Return (level name, points needed for the next level or None at the top)."""
    for index, (floor, name) in enumerate(HEALTH_LEVELS):
        if score >= floor:
            if index == 0:
                return name, None
            return name, int(HEALTH_LEVELS[index - 1][0] - score)
    return HEALTH_LEVELS[-1][1], None


# ---------------------------------------------------------------------------
# Badges and challenges
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Badge:
    key: str
    name: str
    requirement: str
    earned: Callable[..., bool]


BADGES: tuple[Badge, ...] = (
    Badge("salary", "Payday Logged", "Receive your salary this month",
          lambda s: s.income > 0),
    Badge("saver", "Saver Starter", "Move any amount into savings",
          lambda s: s.savings > 0),
    Badge("saver15", "Fifteen Percenter", "Save 15% of your salary",
          lambda s: s.savings_rate >= SAVINGS_GOAL_RATE),
    Badge("black", "In The Black", "End the month with a positive balance",
          lambda s: s.closing_balance >= 0),
    Badge("fees", "Fee Fighter", "Keep bank fees under R200",
          lambda s: s.bank_fees < 200),
    Badge("subs", "Subscription Sniper", "Keep subscriptions under 2% of salary",
          lambda s: s.category_rate("Subscriptions") < 0.02),
    Badge("cash", "Cash Light", "Keep cash withdrawals under 5% of salary",
          lambda s: s.category_rate("Cash Withdrawal") < 0.05),
    Badge("fuel", "Road Smart", "Keep transport under 10% of salary",
          lambda s: s.category_rate("Transport") <= 0.10),
    Badge("clean", "All Clear", "No transactions flagged as unusual",
          lambda s: s.unusual_spend == 0),
    Badge("streak", "Quiet Day", "Get through one full day without spending",
          lambda s: s.no_spend_days >= 1),
    Badge("budget", "Budget Boss", "Stay inside budget in at least 8 categories",
          lambda s: s.categories_within_budget >= 8),
    Badge("rewards", "Rewards Ready", "Have over R500 of Rewards Points within reach",
          lambda s: s.rewards_opportunity > 500),
    Badge("tier3", "Tier Climber", "Reach UCount Tiering Level 3 or better",
          lambda s: s.tiering_level >= 3),
)


@dataclass(frozen=True)
class Challenge:
    name: str
    goal: str
    xp: int
    progress: Callable[..., float]    # snapshot -> 0.0 to 1.0
    status: Callable[..., str]        # snapshot -> short "where you are" line


CHALLENGES: tuple[Challenge, ...] = (
    Challenge(
        "Climb out of the overdraft", "Finish next month at R0 or better", 500,
        lambda s: 1.0 if s.closing_balance >= 0 else 0.0,
        lambda s: f"Closing balance is {rand(s.closing_balance)}",
    ),
    Challenge(
        "Bank 15% of payday", "Move 15% of your salary to savings on payday", 400,
        lambda s: min(1.0, s.savings / max(s.savings_goal, 1)),
        lambda s: f"Saved {rand(s.savings)} of {rand(s.savings_goal)}",
    ),
    Challenge(
        "Starve the fee monster", "Keep total bank fees under R100", 200,
        lambda s: min(1.0, 100 / s.bank_fees) if s.bank_fees else 1.0,
        lambda s: f"Paid {rand(s.bank_fees)} in fees",
    ),
    Challenge(
        "Shop the rewards way", "Earn back the Rewards Points you are missing", 300,
        lambda s: 0.0 if s.rewards_opportunity else 1.0,
        lambda s: f"About {rand(s.rewards_opportunity, 0)} sitting unclaimed",
    ),
    Challenge(
        "Colour every bar blue", "Finish inside budget in all 12 categories", 250,
        lambda s: s.categories_within_budget / max(len(CATEGORY_BUDGETS), 1),
        lambda s: f"{s.categories_within_budget} of {len(CATEGORY_BUDGETS)} inside budget",
    ),
    Challenge(
        "Keep it clean", "No transactions in the unusual category", 350,
        lambda s: 1.0 if s.unusual_spend == 0 else 0.0,
        lambda s: f"{s.unusual_count} transaction(s) flagged this month",
    ),
)


# ---------------------------------------------------------------------------
# Proactive balance notifications
# ---------------------------------------------------------------------------

#: Available funds for the month = what was in the account on day one plus the
#: salary. Spending is measured against that, and each threshold below fires
#: once, the first time cumulative spending crosses it.
AVAILABLE_FUNDS_RULE = "opening balance + salary"


@dataclass(frozen=True)
class AlertRule:
    threshold: float          # share of available funds spent
    level: str                # info | warning | critical | offer
    title: str
    body: str                 # formatted with the context the engine builds
    action: str = ""


ALERT_RULES: tuple[AlertRule, ...] = (
    AlertRule(
        0.50, "info", "Half of this month's money is spent",
        "You have spent {used} of the {available} available this month. "
        "{remaining} is left with {days_left} days to go, which is about "
        "{daily_budget} a day.",
        "Nothing to do yet. Worth knowing where you are.",
    ),
    AlertRule(
        0.75, "warning", "Three quarters spent, commitments still to come",
        "{used} of {available} is now gone, leaving {remaining}. {upcoming}",
        "Set aside what the scheduled payments need before spending the rest.",
    ),
    AlertRule(
        0.90, "critical", "Running low",
        "Only {remaining} of your {available} is left and there are {days_left} "
        "days to go. You are spending about {pace} a day, so at this pace the "
        "account runs empty before month end.",
        "Hold off on anything that is not essential until payday.",
    ),
    AlertRule(
        0.95, "offer", "Five percent left",
        "{remaining} remains with {days_left} days until payday. A credit card "
        "or a higher limit on an existing card can cover a short gap, but it is "
        "borrowing, not income.",
        "See the affordability check below before taking this up.",
    ),
)

LEVEL_ORDER = ("info", "warning", "critical", "offer")


# ---------------------------------------------------------------------------
# Credit card eligibility (the 95% notification)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CreditCheck:
    name: str
    requirement: str
    passes: Callable[..., bool]


#: A pre-qualified offer needs most of these. Fewer, and the app routes the
#: customer to a banker rather than pretending to approve anything.
CREDIT_CHECKS: tuple[CreditCheck, ...] = (
    CreditCheck("Regular income", "A salary deposit lands every month",
                lambda s: s.income > 0),
    CreditCheck("Positive month end", "The account closes at R0 or better",
                lambda s: s.closing_balance >= 0),
    CreditCheck("Saving something", "At least 5% of salary goes to savings",
                lambda s: s.savings_rate >= 0.05),
    CreditCheck("Commitments under control",
                "Loans, debit orders and insurance stay under 40% of salary",
                lambda s: s.commitment_rate < 0.40),
    CreditCheck("Clean account", "No transactions flagged as unusual",
                lambda s: s.unusual_spend == 0),
)

CREDIT_PREQUALIFY_MIN = 4       # checks that must pass for an indicative offer
CREDIT_LIMIT_RATE = 1.0         # indicative limit = one month of disposable income
CREDIT_LIMIT_STEP = 500         # rounded down to the nearest R500
CREDIT_LIMIT_FLOOR = 2_000
CREDIT_LIMIT_CAP = 30_000

CREDIT_DISCLAIMER = (
    "Indicative only. Any card or limit increase is subject to a full "
    "affordability assessment and credit approval under the National Credit Act.")


def indicative_limit(snapshot) -> float:
    """Disposable income = salary less commitments and essential spending."""
    essentials = (snapshot.category_totals.get("Groceries", 0.0)
                  + snapshot.category_totals.get("Transport", 0.0))
    disposable = snapshot.income - snapshot.commitments - essentials
    limit = disposable * CREDIT_LIMIT_RATE
    limit = (limit // CREDIT_LIMIT_STEP) * CREDIT_LIMIT_STEP
    return max(CREDIT_LIMIT_FLOOR, min(CREDIT_LIMIT_CAP, limit))
