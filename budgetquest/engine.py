"""Rule-based analytics.

Reads a Statement, applies the rule book, returns one `Insights` object that
the UI renders. Arithmetic and if/then only -- no models, no training, no
inference. Anything the app claims can be recomputed by hand from this file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from . import rewards, rules
from .formatting import rand
from .models import Statement, Transaction


# ---------------------------------------------------------------------------
# Aggregates
# ---------------------------------------------------------------------------

@dataclass
class Snapshot:
    """Raw totals for the statement period. Everything else derives from this."""

    income: float = 0.0
    refunds: float = 0.0
    total_spend: float = 0.0
    savings: float = 0.0
    bank_fees: float = 0.0
    discretionary: float = 0.0
    commitments: float = 0.0
    unusual_spend: float = 0.0
    unusual_count: int = 0
    opening_balance: float = 0.0
    closing_balance: float = 0.0
    days: int = 30
    no_spend_days: int = 0
    longest_no_spend_streak: int = 0
    biggest_purchase: Transaction | None = None
    category_totals: dict[str, float] = field(default_factory=dict)
    category_counts: dict[str, int] = field(default_factory=dict)
    daily_spend: dict = field(default_factory=dict)

    # UCount tiering inputs, all read straight off the statement
    average_balance: float = 0.0
    deposits: float = 0.0
    debit_order_count: int = 0
    home_loans: int = 0
    vehicle_finance: int = 0
    sb_insurance: int = 0
    subscriptions: int = 0
    credit_card_subscriptions: int = 0
    digital_payments: int = 0
    credit_card_share: float = 0.0

    # filled in once the budget, merchant and tiering reports are built
    categories_within_budget: int = 0
    rewards_opportunity: float = 0.0
    tiering_level: int = 1

    # -- ratios the rule book reads ----------------------------------------
    def rate(self, amount: float) -> float:
        return amount / self.income if self.income else 0.0

    def category_rate(self, name: str) -> float:
        return self.rate(self.category_totals.get(name, 0.0))

    @property
    def savings_rate(self) -> float:
        return self.rate(self.savings)

    @property
    def discretionary_rate(self) -> float:
        return self.rate(self.discretionary)

    @property
    def commitment_rate(self) -> float:
        return self.rate(self.commitments)

    @property
    def unusual_rate(self) -> float:
        return self.rate(self.unusual_spend)

    @property
    def spend_rate(self) -> float:
        return self.rate(self.total_spend)

    @property
    def savings_goal(self) -> float:
        return self.income * rules.SAVINGS_GOAL_RATE

    @property
    def discretionary_budget(self) -> float:
        return rules.budget_for("Discretionary Spending", self.income)

    @property
    def available_funds(self) -> float:
        """What there was to spend this month: opening balance plus salary."""
        return self.opening_balance + self.income

    @property
    def funds_used(self) -> float:
        return (self.total_spend / self.available_funds
                if self.available_funds > 0 else 0.0)

    @property
    def net(self) -> float:
        return self.income + self.refunds - self.total_spend


def build_snapshot(statement: Statement) -> Snapshot:
    snap = Snapshot(
        opening_balance=statement.account.opening_balance,
        closing_balance=statement.account.closing_balance,
        days=statement.account.days,
    )
    spend_days = set()

    for txn in statement.transactions:
        if txn.is_credit:
            if txn.category in rules.INCOME_CATEGORIES:
                snap.income += txn.inflow
            elif txn.category in rules.REFUND_CATEGORIES:
                snap.refunds += txn.inflow
            continue

        amount = txn.outflow
        snap.total_spend += amount
        snap.category_totals[txn.category] = (
            snap.category_totals.get(txn.category, 0.0) + amount)
        snap.category_counts[txn.category] = (
            snap.category_counts.get(txn.category, 0) + 1)
        snap.daily_spend[txn.day] = snap.daily_spend.get(txn.day, 0.0) + amount
        spend_days.add(txn.day)

        if rules.SAVINGS_NARRATIVE in txn.narrative.upper():
            snap.savings += amount
        if txn.category == "Bank Fees":
            snap.bank_fees += amount
        if txn.category == "Discretionary Spending":
            snap.discretionary += amount
        if txn.category in ("Fixed Commitments", "Debit Order"):
            snap.commitments += amount
        if txn.category_id == 199:
            snap.unusual_spend += amount
            snap.unusual_count += 1
        if snap.biggest_purchase is None or amount > snap.biggest_purchase.outflow:
            snap.biggest_purchase = txn

    snap.no_spend_days, snap.longest_no_spend_streak = _no_spend_streak(
        statement, spend_days)
    _count_tiering_inputs(statement, snap)
    return snap


def _count_tiering_inputs(statement: Statement, snap: Snapshot) -> None:
    """Derive the UCount tiering inputs from the statement itself.

    Everything here is a keyword or category match on rows that are already
    on the statement. Nothing is assumed about products the customer might
    hold elsewhere.
    """
    debit_orders: set[str] = set()
    for txn in statement.transactions:
        narrative = txn.narrative.upper()
        if txn.is_credit and txn.category in rules.INCOME_CATEGORIES + rules.REFUND_CATEGORIES:
            snap.deposits += txn.inflow
        if not txn.is_debit:
            continue
        if txn.category == "Debit Order" or "DEBIT ORDER" in narrative:
            debit_orders.add(rules.merchant_of(txn.narrative))
        if any(word in narrative for word in rules.HOME_LOAN_KEYWORDS):
            snap.home_loans += 1
        if any(word in narrative for word in rules.VEHICLE_FINANCE_KEYWORDS):
            snap.vehicle_finance += 1
        if any(word in narrative for word in rules.SB_INSURANCE_KEYWORDS):
            snap.sb_insurance += 1
        if txn.category == "Subscriptions":
            snap.subscriptions += 1
        if any(word in narrative for word in rules.DIGITAL_PAYMENT_KEYWORDS):
            snap.digital_payments += 1

    snap.debit_order_count = len(debit_orders)
    snap.average_balance = _average_daily_balance(statement)
    # This is a current account: no credit card rows appear on it at all.
    snap.credit_card_subscriptions = 0
    snap.credit_card_share = 0.0


def _average_daily_balance(statement: Statement) -> float:
    """Mean of the closing balance on each day of the statement period."""
    first = statement.account.period_from.date()
    last = statement.account.period_to.date()
    closing: dict = {}
    for txn in statement.transactions:
        closing[txn.day] = txn.running_balance

    balance = statement.account.opening_balance
    day, total, days = first, 0.0, 0
    while day <= last:
        balance = closing.get(day, balance)
        total += balance
        days += 1
        day += timedelta(days=1)
    return total / days if days else 0.0


def _no_spend_streak(statement: Statement, spend_days: set) -> tuple[int, int]:
    """Count quiet days, and the longest unbroken run of them."""
    day = statement.account.period_from.date()
    last = statement.account.period_to.date()
    total = streak = best = 0
    while day <= last:
        if day in spend_days:
            streak = 0
        else:
            total += 1
            streak += 1
            best = max(best, streak)
        day += timedelta(days=1)
    return total, best


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CategoryLine:
    name: str
    total: float
    count: int
    share_of_income: float
    budget: float
    colour: str

    @property
    def usage(self) -> float:
        return self.total / self.budget if self.budget else 2.0

    @property
    def status(self) -> str:
        if not self.budget:
            return "over"
        if self.usage > 1.0:
            return "over"
        if self.usage >= 0.85:
            return "near"
        return "under"

    @property
    def remaining(self) -> float:
        return self.budget - self.total


@dataclass(frozen=True)
class MerchantLine:
    label: str
    category: str
    total: float
    count: int
    share_of_income: float
    tip: rewards.RewardTip
    scheme: rewards.EarnScheme
    tier: int
    card: str = "credit"

    @property
    def average(self) -> float:
        return self.total / self.count if self.count else 0.0

    @property
    def switchable(self) -> float:
        """The slice of this spend that could realistically move to a partner."""
        return self.total * self.tip.share

    def estimate_at(self, tier: int, card: str | None = None) -> float:
        return rewards.earn(self.switchable, self.scheme, tier, card or self.card)

    @property
    def estimate(self) -> float:
        return self.estimate_at(self.tier)


@dataclass(frozen=True)
class TieringLine:
    rule: rewards.TieringRule
    points: int
    evidence: str

    @property
    def headroom(self) -> int:
        return max(0, self.rule.cap - self.points)


@dataclass(frozen=True)
class TierReport:
    lines: tuple[TieringLine, ...]
    points: int
    level: int
    points_to_next: int | None

    @property
    def available(self) -> int:
        """Points still on the table across every rule."""
        return sum(line.headroom for line in self.lines)


@dataclass(frozen=True)
class RewardsReport:
    """What the merchant mix would earn at each of the five tiering levels."""

    cyor_family: str
    cyor_spend: float
    ladder: tuple[float, ...]          # rand value, tier 1 to tier 5
    debit_at_current: float
    tier: int

    @property
    def current(self) -> float:
        return self.ladder[self.tier - 1]

    @property
    def best(self) -> float:
        return self.ladder[-1]

    @property
    def uplift(self) -> float:
        return self.best - self.current


@dataclass(frozen=True)
class FraudFinding:
    txn: Transaction
    hits: tuple[rules.FraudRule, ...]

    @property
    def escalate(self) -> bool:
        return len(self.hits) >= rules.FRAUD_ESCALATION_HITS

    @property
    def verdict(self) -> str:
        return ("Escalate to the Fraud department" if self.escalate
                else "Monitor, do not escalate")


@dataclass(frozen=True)
class SettlementLine:
    txn: Transaction
    lag_hours: float

    @property
    def within_sla(self) -> bool:
        return self.lag_hours <= rules.SETTLEMENT_SLA_HOURS


@dataclass(frozen=True)
class Alert:
    """One balance notification, and the transaction that triggered it."""

    rule: rules.AlertRule
    txn: Transaction
    used: float
    available: float
    days_left: int
    message: str

    @property
    def remaining(self) -> float:
        return self.available - self.used

    @property
    def share(self) -> float:
        return self.used / self.available if self.available else 0.0


@dataclass(frozen=True)
class CreditOffer:
    """The outcome of the 95% notification's affordability check."""

    checks: tuple[tuple[rules.CreditCheck, bool], ...]
    limit: float
    triggered: bool

    @property
    def passed(self) -> int:
        return sum(1 for _, ok in self.checks if ok)

    @property
    def prequalified(self) -> bool:
        return self.passed >= rules.CREDIT_PREQUALIFY_MIN

    @property
    def outcome(self) -> str:
        if not self.triggered:
            return "Not offered. Spending stayed below 95% of available funds."
        if self.prequalified:
            return "Pre-qualified for an indicative limit, subject to approval."
        return "Refer to a banker. This month's figures do not support an offer."


@dataclass(frozen=True)
class ScoreLine:
    name: str
    points: float
    max_points: float
    rule_text: str


def build_categories(snap: Snapshot) -> list[CategoryLine]:
    lines = [
        CategoryLine(
            name=name,
            total=total,
            count=snap.category_counts.get(name, 0),
            share_of_income=snap.rate(total),
            budget=rules.budget_for(name, snap.income),
            colour=rules.colour_for(name),
        )
        for name, total in snap.category_totals.items()
    ]
    lines.sort(key=lambda line: line.total, reverse=True)
    return lines


def build_tiering(snap: Snapshot) -> TierReport:
    """Score the statement against the UCount tiering point table."""
    lines = []
    for rule in rewards.TIERING_RULES:
        points, evidence = rule.award(snap)
        lines.append(TieringLine(rule, min(points, rule.cap), evidence))
    total = sum(line.points for line in lines)
    level, to_next = rewards.tier_for_points(total)
    return TierReport(tuple(lines), total, level, to_next)


def build_merchants(statement: Statement, snap: Snapshot,
                    tier: int) -> tuple[list[MerchantLine], str, float]:
    """Group debits by merchant and attach the earn scheme that applies.

    Choose Your Own Rewards only pays on one category, so the category with
    the most qualifying spend is picked and the other two fall back to the
    plain card rate.
    """
    grouped: dict[str, dict] = {}
    for txn in statement.transactions:
        if not txn.is_debit:
            continue
        key = rules.merchant_of(txn.narrative)
        bucket = grouped.setdefault(
            key, {"total": 0.0, "count": 0, "category": txn.category,
                  "narrative": txn.narrative})
        bucket["total"] += txn.outflow
        bucket["count"] += 1

    tips = {key: rewards.tip_for(bucket["narrative"])
            for key, bucket in grouped.items()}

    family_spend: dict[str, float] = {name: 0.0 for name in rewards.CYOR_FAMILIES}
    for key, bucket in grouped.items():
        family = rewards.scheme_for(tips[key].scheme).cyor_family
        if family:
            family_spend[family] += bucket["total"]
    best_family = max(family_spend, key=family_spend.get)

    lines = []
    for key, bucket in grouped.items():
        tip = tips[key]
        scheme = rewards.scheme_for(tip.scheme)
        if scheme.cyor_family and scheme.cyor_family != best_family:
            scheme = rewards.CARD_BASE
        lines.append(MerchantLine(
            label=key, category=bucket["category"], total=bucket["total"],
            count=bucket["count"], share_of_income=snap.rate(bucket["total"]),
            tip=tip, scheme=scheme, tier=tier,
        ))
    lines.sort(key=lambda line: line.total, reverse=True)
    return lines, best_family, family_spend[best_family]


def build_rewards(merchants: list[MerchantLine], best_family: str,
                  cyor_spend: float, tier: int) -> RewardsReport:
    ladder = tuple(
        sum(line.estimate_at(level, "credit") for line in merchants)
        for level in range(1, rewards.TIER_COUNT + 1)
    )
    debit_now = sum(line.estimate_at(tier, "debit") for line in merchants)
    return RewardsReport(best_family, cyor_spend, ladder, debit_now, tier)


def build_fraud(statement: Statement, snap: Snapshot) -> list[FraudFinding]:
    findings = []
    for txn in statement.transactions:
        hits = tuple(rule for rule in rules.FRAUD_RULES if rule.check(txn, snap.income))
        if hits:
            findings.append(FraudFinding(txn, hits))
    findings.sort(key=lambda f: (len(f.hits), f.txn.outflow), reverse=True)
    return findings


def build_settlements(statement: Statement) -> list[SettlementLine]:
    lines = [SettlementLine(txn, txn.settlement_hours) for txn in statement.transactions]
    lines.sort(key=lambda line: line.lag_hours, reverse=True)
    return lines


def _commitments_after(statement: Statement, txn: Transaction) -> list[Transaction]:
    """Scheduled payments still due after this point in the month."""
    return [other for other in statement.transactions
            if rules.is_commitment(other)
            and other.transaction_date > txn.transaction_date]


def build_alerts(statement: Statement, snap: Snapshot) -> list[Alert]:
    """Walk the month in order and fire each threshold the first time it is crossed."""
    available = snap.available_funds
    if available <= 0:
        return []

    ordered = sorted(rules.ALERT_RULES, key=lambda rule: rule.threshold)
    last_day = statement.account.period_to.date()
    first_day = statement.account.period_from.date()
    alerts: list[Alert] = []
    used = 0.0
    position = 0

    for txn in statement.transactions:
        if not txn.is_debit:
            continue
        used += txn.outflow
        while position < len(ordered) and used >= available * ordered[position].threshold:
            rule = ordered[position]
            position += 1
            days_left = max((last_day - txn.day).days, 0)
            days_gone = max((txn.day - first_day).days + 1, 1)
            remaining = available - used
            upcoming = _commitments_after(statement, txn)
            alerts.append(Alert(
                rule=rule, txn=txn, used=used, available=available,
                days_left=days_left,
                message=rule.body.format(
                    used=rand(used), available=rand(available),
                    remaining=rand(remaining), days_left=days_left,
                    daily_budget=rand(remaining / days_left) if days_left else rand(0),
                    pace=rand(used / days_gone),
                    upcoming=_upcoming_line(upcoming, days_left),
                ),
            ))
    return alerts


def _upcoming_line(upcoming: list[Transaction], days_left: int) -> str:
    """The sentence the 75% warning uses to name what is still owed."""
    if not upcoming:
        return (f"Every scheduled payment for the month has already gone off, so "
                f"what is left has to cover {days_left} days of day-to-day spending.")
    total = sum(txn.outflow for txn in upcoming)
    names = ", ".join(sorted({rules.merchant_of(txn.narrative).title()
                              for txn in upcoming}))
    return (f"Still due before month end: {rand(total)} across "
            f"{len(upcoming)} scheduled payments ({names}).")


def build_credit_offer(snap: Snapshot, alerts: list[Alert]) -> CreditOffer:
    triggered = any(alert.rule.level == "offer" for alert in alerts)
    checks = tuple((check, bool(check.passes(snap))) for check in rules.CREDIT_CHECKS)
    return CreditOffer(checks, rules.indicative_limit(snap), triggered)


def build_score(snap: Snapshot) -> tuple[list[ScoreLine], float]:
    lines = []
    for rule in rules.SCORE_RULES:
        fraction = max(0.0, min(1.0, rule.score(snap)))
        lines.append(ScoreLine(rule.name, round(rule.max_points * fraction, 1),
                               rule.max_points, rule.rule_text))
    return lines, round(sum(line.points for line in lines))


# ---------------------------------------------------------------------------
# One object for the whole UI
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Insights:
    statement: Statement
    snapshot: Snapshot
    categories: tuple[CategoryLine, ...]
    merchants: tuple[MerchantLine, ...]
    fraud: tuple[FraudFinding, ...]
    settlements: tuple[SettlementLine, ...]
    score_lines: tuple[ScoreLine, ...]
    score: float
    health_level: str
    points_to_next_level: int | None
    tiering: TierReport
    rewards_report: RewardsReport
    badges: tuple[tuple[rules.Badge, bool], ...]
    challenges: tuple[tuple[rules.Challenge, float, str], ...]
    alerts: tuple[Alert, ...]
    credit_offer: CreditOffer

    @property
    def escalations(self) -> tuple[FraudFinding, ...]:
        return tuple(finding for finding in self.fraud if finding.escalate)

    @property
    def late_settlements(self) -> tuple[SettlementLine, ...]:
        return tuple(line for line in self.settlements if not line.within_sla)

    @property
    def alert_level(self) -> str:
        """The most serious notification reached this month."""
        if not self.alerts:
            return "none"
        return max((alert.rule.level for alert in self.alerts),
                   key=rules.LEVEL_ORDER.index)

    @property
    def xp(self) -> int:
        """100 XP per badge earned, plus one XP per health point."""
        earned = sum(1 for _, ok in self.badges if ok)
        return int(earned * 100 + self.score)


def analyse(statement: Statement) -> Insights:
    snap = build_snapshot(statement)
    categories = build_categories(snap)

    tiering = build_tiering(snap)
    snap.tiering_level = tiering.level

    merchants, best_family, cyor_spend = build_merchants(
        statement, snap, tiering.level)
    rewards_report = build_rewards(merchants, best_family, cyor_spend,
                                   tiering.level)

    # Snapshot fields that depend on the reports above are set here.
    snap.categories_within_budget = sum(
        1 for line in categories if line.status != "over")
    snap.rewards_opportunity = rewards_report.best

    alerts = build_alerts(statement, snap)
    score_lines, score = build_score(snap)
    level, to_next = rules.health_level_for(score)

    return Insights(
        statement=statement,
        snapshot=snap,
        categories=tuple(categories),
        merchants=tuple(merchants),
        fraud=tuple(build_fraud(statement, snap)),
        settlements=tuple(build_settlements(statement)),
        score_lines=tuple(score_lines),
        score=score,
        health_level=level,
        points_to_next_level=to_next,
        tiering=tiering,
        rewards_report=rewards_report,
        badges=tuple((badge, bool(badge.earned(snap))) for badge in rules.BADGES),
        challenges=tuple(
            (challenge, max(0.0, min(1.0, challenge.progress(snap))),
             challenge.status(snap))
            for challenge in rules.CHALLENGES
        ),
        alerts=tuple(alerts),
        credit_offer=build_credit_offer(snap, alerts),
    )
