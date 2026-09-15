"""The UCount Rewards model.

Split out of `rules.py` because it is a different concern: `rules.py` says
what good budgeting looks like, this module says what Standard Bank's loyalty
programme pays for it. Both are plain data plus arithmetic.

The numbers below are transcribed from the UCount Rewards Programme Rules
(Annexure A, July 2025): five tiering levels, the tiering point table, and the
earn rate tables for card rewards, Choose Your Own Rewards, fuel and the
rewards retailers. Nothing here is estimated by a model — the only assumption
is the average fuel price, which is stated as a constant.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

TIER_COUNT = 5

#: Tiering points needed for each level. Checked from the top down.
TIER_THRESHOLDS: tuple[tuple[int, int], ...] = (
    (5, 875), (4, 725), (3, 575), (2, 400), (1, 0),
)

#: Rewards points are worth 1 cent each, so 100 points = R1.
POINT_VALUE = 0.01

#: Fuel rewards are quoted per litre, so rand spend has to be converted.
#: UCount uses a weighted average pump price; this is a stated stand-in.
FUEL_PRICE_PER_LITRE = 22.00


def tier_for_points(points: int) -> tuple[int, int | None]:
    """Return (tier, points still needed for the next tier or None at Tier 5)."""
    for index, (tier, floor) in enumerate(TIER_THRESHOLDS):
        if points >= floor:
            if index == 0:
                return tier, None
            return tier, TIER_THRESHOLDS[index - 1][1] - points
    return 1, TIER_THRESHOLDS[-2][1] - points



# Earn rate tables


@dataclass(frozen=True)
class EarnScheme:
    """How one kind of spend earns, across the five tiering levels."""

    key: str
    label: str
    credit: tuple[float, float, float, float, float]
    debit: tuple[float, float, float, float, float]
    monthly_cap: float | None = None   # rand of spend that earns at this rate
    cyor_family: str = ""              # grocery | fashion | lifestyle
    per_litre: bool = False            # rates are rands per litre, not a share
    spills_to_base: bool = True        # spend over the cap earns the card rate

    def rate(self, tier: int, card: str = "credit") -> float:
        raw = (self.credit if card == "credit" else self.debit)[tier - 1]
        return raw / FUEL_PRICE_PER_LITRE if self.per_litre else raw


#: Card rewards — the floor every qualifying purchase earns.
CARD_BASE = EarnScheme(
    "card_base", "Card rewards on any purchase",
    credit=(0.0025, 0.0040, 0.0050, 0.0070, 0.0100),
    debit=(0.0005, 0.0010, 0.0012, 0.0015, 0.0025),
    monthly_cap=50_000, spills_to_base=False,
)

_CYOR_DEBIT = (0.0050, 0.0075, 0.0100, 0.0200, 0.0500)
_CYOR_CAP = 3_000


def _flat(key: str, label: str, rate: float, cap: float | None = None) -> EarnScheme:
    """A rewards retailer that pays the same rate at every tier."""
    rates = (rate,) * TIER_COUNT
    return EarnScheme(key, label, rates, rates, monthly_cap=cap)
#end flat

EARN_SCHEMES: dict[str, EarnScheme] = {
    scheme.key: scheme for scheme in (
        CARD_BASE,
        EarnScheme(
            "cyor_grocery_boost", "Checkers and Shoprite in store",
            credit=(0.03, 0.04, 0.06, 0.15, 0.30), debit=_CYOR_DEBIT,
            monthly_cap=_CYOR_CAP, cyor_family="grocery",
        ),
        EarnScheme(
            "cyor_grocery", "Grocery rewards at other partners",
            credit=(0.02, 0.03, 0.04, 0.10, 0.20), debit=_CYOR_DEBIT,
            monthly_cap=_CYOR_CAP, cyor_family="grocery",
        ),
        EarnScheme(
            "cyor_fashion", "Fashion rewards",
            credit=(0.02, 0.03, 0.04, 0.10, 0.20), debit=_CYOR_DEBIT,
            monthly_cap=_CYOR_CAP, cyor_family="fashion",
        ),
        EarnScheme(
            "cyor_lifestyle", "Lifestyle rewards",
            credit=(0.02, 0.03, 0.04, 0.10, 0.20), debit=_CYOR_DEBIT,
            monthly_cap=_CYOR_CAP, cyor_family="lifestyle",
        ),
        EarnScheme(
            "fuel", "Fuel rewards per litre",
            credit=(0.30, 0.45, 0.90, 1.50, 5.00),
            debit=(0.10, 0.15, 0.30, 0.50, 1.00),
            monthly_cap=2_500, per_litre=True, spills_to_base=False,
        ),
        EarnScheme(
            "netstar", "Netstar vehicle tracking",
            credit=(0.005, 0.01, 0.05, 0.075, 0.12),
            debit=(0.005, 0.01, 0.05, 0.075, 0.12),
        ),
        _flat("kfc", "KFC", 0.01),
        _flat("freshstop", "FreshStop at Caltex", 0.0125),
        _flat("makro", "Makro general merchandise", 0.0075, cap=66_666),
        _flat("game", "Game", 0.0075, cap=66_666),
        _flat("hirsch", "Hirsch's", 0.01),
        _flat("tiger", "Tiger Wheel and Tyre", 0.025),
        _flat("car_service", "Car Service City", 0.03),
        _flat("wine_club", "Wine-of-the-Month Club", 0.02),
        _flat("none", "Earns nothing", 0.0),
    )
}

CYOR_FAMILIES = ("grocery", "fashion", "lifestyle")
CYOR_FAMILY_LABELS = {
    "grocery": "Grocery rewards",
    "fashion": "Fashion rewards",
    "lifestyle": "Lifestyle rewards",
}


def scheme_for(key: str) -> EarnScheme:
    return EARN_SCHEMES.get(key, CARD_BASE)


def earn(spend: float, scheme: EarnScheme, tier: int, card: str = "credit") -> float:
    """Rand value of rewards points on `spend`, honouring the monthly cap.

    Spend above a Choose Your Own Rewards cap keeps earning, but at the plain
    card rate. Fuel and card rewards do not spill over.
    """
    if spend <= 0:
        return 0.0
    capped = min(spend, scheme.monthly_cap) if scheme.monthly_cap else spend
    value = capped * scheme.rate(tier, card)
    overflow = spend - capped
    if overflow > 0 and scheme.spills_to_base:
        value += overflow * CARD_BASE.rate(tier, card)
    return value


# ---------------------------------------------------------------------------
# Merchant recognition and advice
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RewardTip:
    """A saving idea for one merchant or service.

    `share` is how much of that spend could realistically move to the partner
    in a normal month. The earn rate itself is never guessed — it comes from
    the scheme's published table.
    """

    keywords: tuple[str, ...]
    partner: str
    headline: str
    advice: str
    scheme: str = "card_base"
    share: float = 1.0

    def matches(self, narrative: str) -> bool:
        upper = narrative.upper()
        return any(keyword in upper for keyword in self.keywords)


#: Ordered: the first match wins, so specific keywords go above generic ones.
REWARD_TIPS: tuple[RewardTip, ...] = (
    RewardTip(
        ("WOOLWORTHS",), "Checkers and Shoprite",
        "Up to 30% back in store, against Woolworths' 20%",
        "Woolworths is a participating grocery retailer, so this spend already "
        "qualifies for Choose Your Own Rewards. Checkers and Shoprite pay a "
        "boosted rate on the same basket, and Sixty60 pays more again.",
        scheme="cyor_grocery_boost", share=0.60,
    ),
    RewardTip(
        ("FUEL STATION", "PETROL", "GARAGE"), "Astron Energy and Caltex",
        "From 30c to R5 a litre back, by tier",
        "Fuel rewards climb faster with tier than anything else on your "
        "statement. On a credit card at Tier 5 the pump effectively discounts "
        "itself, and you can pay for fuel with the points you banked.",
        scheme="fuel", share=1.00,
    ),
    RewardTip(
        ("GYM",), "Planet Fitness, Virgin Active, Viva Gym",
        "Gym debit orders count as lifestyle rewards",
        "The programme rules treat a gym membership paid by debit order as a "
        "qualifying lifestyle purchase, so this is one of the few commitments "
        "on the statement that can earn at a Choose Your Own Rewards rate.",
        scheme="cyor_lifestyle", share=1.00,
    ),
    RewardTip(
        ("RESTAURANT",), "Ocean Basket, Turn 'n Tender, Mugg & Bean",
        "Sit-down meals count as lifestyle rewards",
        "A long list of restaurants are participating lifestyle retailers. "
        "Choosing where to eat from that list costs nothing and turns the same "
        "meal into points.",
        scheme="cyor_lifestyle", share=0.60,
    ),
    RewardTip(
        ("FAST FOOD", "TAKEAWAY"), "Steers, Debonairs, Roman's, KFC",
        "Lifestyle rewards, or 1% flat at KFC",
        "Most of the big takeaway brands are participating lifestyle "
        "retailers, and KFC pays a flat rate on top as a rewards retailer.",
        scheme="cyor_lifestyle", share=0.70,
    ),
    RewardTip(
        ("COFFEE SHOP",), "Mugg & Bean, Fego Caffé, Vovo Telo",
        "Coffee counts as lifestyle rewards",
        "Five coffee stops a month is small money that adds up. All three of "
        "these chains are participating lifestyle retailers.",
        scheme="cyor_lifestyle", share=0.60,
    ),
    RewardTip(
        ("BAR", "NIGHT OUT"), "Wine-of-the-Month Club",
        "2% back at every tier",
        "Bar tabs earn only the card rate. This is the most discretionary line "
        "on your statement, so the real saving here is spending less of it.",
        scheme="wine_club", share=0.30,
    ),
    RewardTip(
        ("CLOTHING", "FASHION"), "Foschini, Edgars, Jet, Woolworths",
        "Fashion rewards, up to 20% at Tier 5",
        "Clothing only earns the boosted rate if fashion is the Choose Your "
        "Own Rewards category you picked, and you can only pick one.",
        scheme="cyor_fashion", share=0.80,
    ),
    RewardTip(
        ("ELECTRONICS",), "Hirsch's, Samsung, Game",
        "1% at Hirsch's, 0.75% at Game",
        "Electronics sits outside Choose Your Own Rewards, so it earns a flat "
        "rewards retailer rate. Worth timing a big purchase for when you have "
        "points to redeem rather than spend.",
        scheme="hirsch", share=0.70,
    ),
    RewardTip(
        ("FURNITURE",), "Makro and Hirsch's",
        "0.75% to 1% on general merchandise",
        "A once-off of this size is exactly what banked points are for. Buying "
        "it at a rewards retailer earns on the full amount and lets you redeem "
        "points against the price.",
        scheme="makro", share=0.50,
    ),
    RewardTip(
        ("TAKEALOT",), "Makro online and Game",
        "0.75% at a rewards retailer, against the card rate elsewhere",
        "Takealot is not a rewards retailer, and the Takealot virtual card is "
        "explicitly excluded from earning. Price-check Makro and Game first.",
        scheme="makro", share=0.60,
    ),
    RewardTip(
        ("VEHICLE FINANCE",), "Tiger Wheel & Tyre, Car Service City, Netstar",
        "2.5% to 3% on tyres and servicing",
        "The finance instalment itself cannot earn. Everything around the car "
        "can: tyres, servicing and tracking are all rewards retailers, and "
        "vehicle finance also earns you tiering points every month.",
        scheme="tiger", share=0.0,
    ),
    RewardTip(
        ("STREAMING", "MUSIC APP", "NEWS DIGITAL", "CLOUD STORAGE", "APP STORE"),
        "Netflix, Spotify, Apple, YouTube, Disney+",
        "Tiering points, not rewards points",
        "Subscriptions pay you in tiering points rather than cash back: load "
        "up to three on a qualifying Standard Bank credit card and that is 75 "
        "tiering points every month, which lifts your earn rate everywhere.",
        scheme="card_base", share=1.00,
    ),
    RewardTip(
        ("HOME LOAN",), "Standard Bank savings products",
        "75 tiering points a month, and a place to redeem",
        "Your largest debit cannot earn rewards points, but holding the home "
        "loan is worth 75 tiering points every month, and points redeem into "
        "PureSave, Notice Deposit or a Tax-Free Investment account.",
        scheme="none", share=0.0,
    ),
    RewardTip(
        ("MEDICAL AID", "LIFE INSURANCE", "SHORT-TERM INSURANCE"),
        "Standard Bank and Liberty policies",
        "25 to 50 tiering points per policy, per month",
        "Insurance premiums earn no rewards points, but a qualifying Standard "
        "Bank or Liberty policy earns tiering points, which raise the rate you "
        "earn everywhere else. Policies with other insurers earn nothing.",
        scheme="none", share=0.0,
    ),
    RewardTip(
        ("ATM CASH WITHDRAWAL",), "Pay by card instead",
        "Cash earns nothing and costs a fee",
        "Every rand drawn as cash earns zero rewards points and triggers a "
        "withdrawal fee. The same spend on card earns at your tier rate and "
        "costs nothing.",
        scheme="card_base", share=1.00,
    ),
    RewardTip(
        ("E-TOLL",), "Admyt", "Points redeem against parking and tolls",
        "E-tolls earn only the card rate, but Admyt is a redemption partner, "
        "so banked points can pay for parking.",
        scheme="card_base", share=1.00,
    ),
    RewardTip(
        ("CELLPHONE",), "Qualifying Standard Bank card",
        "Card rate, plus tiering points on the contract",
        "Contract payments earn the plain card rate. Buying the next upgrade "
        "at a rewards retailer earns considerably more.",
        scheme="card_base", share=1.00,
    ),
    RewardTip(
        ("GAMING", "CRYPTO", "UNRECOGNISED", "INTERNATIONAL"),
        "Flagged for review",
        "No rewards while this is under investigation",
        "This merchant has been escalated to the Fraud department. It is "
        "excluded from the rewards estimate until the bank confirms the "
        "outcome.",
        scheme="none", share=0.0,
    ),
    RewardTip(
        ("FEE", "NOTICE"), "Not a rewards retailer",
        "The most reliable saving on the statement",
        "Fees earn nothing and are pure loss. Withdrawal fees and the "
        "overdrawn notice fee are avoidable by paying on card and keeping the "
        "balance positive.",
        scheme="none", share=0.0,
    ),
    RewardTip(
        ("SAVINGS POCKET",), "Standard Bank PureSave",
        "50 tiering points for a R1 000 average balance",
        "The healthiest line on your statement, and it pays twice: it moves "
        "your savings goal and it earns tiering points once the average "
        "balance holds above R1 000.",
        scheme="none", share=0.0,
    ),
    RewardTip(
        ("FAMILY SUPPORT", "BENEFICIARY"), "Counts as a digital transaction",
        "Tiering points for app-initiated payments",
        "Payments you initiate in the app count towards the digital tiering "
        "rule. Five or more a month is 25 points, twenty-five or more is 100.",
        scheme="none", share=0.0,
    ),
)

DEFAULT_TIP = RewardTip(
    (), "Qualifying Standard Bank card",
    "Card rewards at your tier rate",
    "No dedicated rewards retailer covers this spend, so the plain card rate "
    "applies. It still beats cash, which earns nothing at all.",
    scheme="card_base", share=1.00,
)


def tip_for(narrative: str) -> RewardTip:
    for tip in REWARD_TIPS:
        if tip.matches(narrative):
            return tip
    return DEFAULT_TIP



# Tiering points, derived from what the statement can actually show


@dataclass(frozen=True)
class TieringRule:
    """One row of the UCount tiering point table.

    `award` returns the points earned plus a short line of evidence, both
    computed from the statement. `action` says how to earn the rest.
    """

    code: str
    name: str
    basis: str
    cap: int
    award: Callable[..., tuple[int, str]]
    action: str = ""


def _banded(value: float, bands: tuple[tuple[float, int], ...]) -> int:
    """Highest band whose floor the value reaches. Bands run low to high."""
    points = 0
    for floor, award in bands:
        if value >= floor:
            points = award
    return points


TIERING_RULES: tuple[TieringRule, ...] = (
    TieringRule(
        "T7", "Average current account balance",
        "Average monthly balance across transactional accounts", 125,
        lambda s: (
            _banded(s.average_balance, ((10_000, 50), (15_000, 75),
                                        (30_000, 100), (50_000, 125))),
            f"Averaged {s.average_balance:,.0f} over the month",
        ),
        "Holding an average of R30 000 would be worth another 25 points.",
    ),
    TieringRule(
        "T8", "Debit orders and deposits",
        "Three or more debit orders plus total monthly deposits", 125,
        lambda s: (
            _banded(s.deposits, ((10_000, 50), (21_000, 75),
                                 (43_000, 100), (63_000, 125)))
            if s.debit_order_count >= 3 else 0,
            f"{s.debit_order_count} debit orders, {s.deposits:,.0f} deposited",
        ),
        "Already near the top band. R63 000 of deposits would max it out.",
    ),
    TieringRule(
        "T10", "Home loan",
        "An active Standard Bank home loan with a debit balance", 100,
        lambda s: (100 if s.home_loans >= 2 else 75 if s.home_loans else 0,
                   f"{s.home_loans} home loan on the statement"),
        "",
    ),
    TieringRule(
        "T11", "Vehicle and asset finance",
        "Finance agreements repaid by debit order", 125,
        lambda s: (_banded(s.vehicle_finance, ((1, 50), (2, 75),
                                               (3, 100), (4, 125))),
                   f"{s.vehicle_finance} agreement on the statement"),
        "",
    ),
    TieringRule(
        "T13", "Insurance policies",
        "Qualifying Standard Bank or Liberty policies", 200,
        lambda s: (min(200, s.sb_insurance * 50),
                   f"{s.sb_insurance} qualifying policies identified"),
        "Only Standard Bank and Liberty policies count. Medical aid does not.",
    ),
    TieringRule(
        "T6", "Savings balance",
        "A savings or investment account averaging R1 000 or more", 300,
        lambda s: (50 if s.savings >= 1_000 else 0,
                   f"Moved {s.savings:,.0f} to the savings pocket"),
        "Larger demand balances scale this rule up to 300 points.",
    ),
    TieringRule(
        "T1", "Digital transactions",
        "Payments you start in the app, internet or USSD banking", 100,
        lambda s: (_banded(s.digital_payments, ((5, 25), (10, 50),
                                                (15, 75), (25, 100))),
                   f"{s.digital_payments} app-initiated payments this month"),
        "Five app payments a month starts earning. Twenty-five maxes it.",
    ),
    TieringRule(
        "T2", "Subscriptions on a credit card",
        "Subscriptions loaded on a qualifying credit card", 75,
        lambda s: (_banded(s.credit_card_subscriptions,
                           ((1, 25), (2, 50), (3, 75))),
                   f"{s.subscriptions} subscriptions, none on a credit card"
                   if not s.credit_card_subscriptions else
                   f"{s.credit_card_subscriptions} loaded on a credit card"),
        "Moving three subscriptions onto a credit card is 75 points a month.",
    ),
    TieringRule(
        "T9", "Share of spend on a credit card",
        "Qualifying purchases on credit rather than debit", 125,
        lambda s: (_banded(s.credit_card_share, ((0.50, 75), (0.80, 100),
                                                 (0.90, 125))),
                   f"{s.credit_card_share:.0%} of purchases on a credit card"),
        "This is the single largest block of points available to you.",
    ),
)
