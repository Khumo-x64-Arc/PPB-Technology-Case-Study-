"""Screens.

Each screen subclasses `View` and is appended to `VIEWS` at the bottom. The
application shell builds its navigation by looping over that list, so adding
a seventh screen means writing a class and appending it -- the shell, the
engine and the rule book are untouched.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import customtkinter as ctk

from . import theme
from . import rewards
from .engine import Insights
from .rules import ALERT_RULES, AVAILABLE_FUNDS_RULE
from .formatting import hours, pct, rand, rand_short, shorten, title
from .rules import (CREDIT_DISCLAIMER, CREDIT_PREQUALIFY_MIN,
                    SETTLEMENT_SLA_HOURS)
from .widgets import (BarChart, Card, Chip, DailySpendChart, DonutChart,
                      LegendRow, ProgressRow, ScoreGauge, StatTile,
                      ThresholdMeter, TierLadder, page_heading, scroll_area)

#: Notification level -> the colour it is shown in.
LEVEL_COLOURS = {"info": theme.BLUE, "warning": theme.WARN,
                 "critical": theme.BAD, "offer": theme.NAVY}
LEVEL_WORDS = {"info": "For information", "warning": "Warning",
               "critical": "Critical", "offer": "Credit option"}


class View(ctk.CTkFrame):
    """Base screen. Subclasses implement `build`."""

    name = "View"
    blurb = ""

    def __init__(self, master, insights: Insights):
        super().__init__(master, fg_color=theme.WASH)
        self.insights = insights
        page_heading(self, self.name, self.blurb)
        self.body = scroll_area(self)
        self.build()

    def build(self) -> None:
        raise NotImplementedError

    # -- shared helpers ----------------------------------------------------
    def card(self, title_text: str = "", subtitle: str = "", **kwargs) -> Card:
        widget = Card(self.body, title_text, subtitle, **kwargs)
        widget.pack(fill="x", pady=(0, 16))
        return widget

    @staticmethod
    def text(master, message: str, colour: str = theme.MUTED,
             size: int = theme.BODY, weight: str = "normal", **kwargs) -> ctk.CTkLabel:
        label = ctk.CTkLabel(master, text=message, font=theme.font(size, weight),
                             text_color=colour, anchor="w", justify="left", **kwargs)
        label.pack(fill="x")
        return label


# ---------------------------------------------------------------------------
# 1. Dashboard
# ---------------------------------------------------------------------------

class DashboardView(View):
    name = "Dashboard"
    blurb = "Thirty days of spending, scored against rules you can check yourself."

    def build(self) -> None:
        snap = self.insights.snapshot
        self._hero(snap)
        self._tiles(snap)
        self._goals(snap)
        self._daily(snap)

    def _hero(self, snap) -> None:
        hero = ctk.CTkFrame(self.body, fg_color=theme.NAVY, corner_radius=14)
        hero.pack(fill="x", pady=(0, 16))

        gauge = ScoreGauge(hero)
        gauge.pack(side="left", padx=(26, 14), pady=22)
        gauge.draw(self.insights.score, self.insights.health_level)

        right = ctk.CTkFrame(hero, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True, padx=(6, 26), pady=24)

        overspend = snap.total_spend - snap.income
        headline = (f"You spent {pct(snap.spend_rate, 0)} of your salary."
                    if overspend > 0 else "You finished the month inside your salary.")
        ctk.CTkLabel(right, text=headline, font=theme.font(theme.DISPLAY - 4, "bold"),
                     text_color=theme.WHITE, anchor="w").pack(fill="x")

        detail = (f"That is {rand(overspend)} more than came in, which is why the "
                  f"account closed at {rand(snap.closing_balance)}."
                  if overspend > 0 else
                  f"The account closed at {rand(snap.closing_balance)}.")
        ctk.CTkLabel(right, text=detail, font=theme.font(theme.BODY),
                     text_color=theme.PALE_INK, anchor="w", justify="left",
                     wraplength=520).pack(fill="x", pady=(6, 14))

        earned = sum(1 for _, ok in self.insights.badges if ok)
        chips = ctk.CTkFrame(right, fg_color="transparent")
        chips.pack(fill="x", pady=(0, 12))
        level = self.insights.alert_level
        for text_value in (f"{self.insights.xp} XP",
                           f"{earned} of {len(self.insights.badges)} badges",
                           f"UCount tier {self.insights.tiering.level}",
                           f"{len(self.insights.alerts)} balance alerts"):
            highlight = (text_value.endswith("balance alerts")
                         and level in ("critical", "offer"))
            Chip(chips, text_value,
                 fill=theme.BAD if highlight else theme.NAVY_SOFT,
                 text_colour=theme.WHITE).pack(side="left", padx=(0, 8))

        to_next = self.insights.points_to_next_level
        if to_next:
            bar = ctk.CTkProgressBar(right, height=8, corner_radius=4,
                                     fg_color=theme.NAVY_SOFT, progress_color=theme.SKY)
            bar.set(self.insights.score / 100)
            bar.pack(fill="x")
            ctk.CTkLabel(right, text=f"{to_next} more health points reach the next level",
                         font=theme.font(theme.CAPTION), text_color=theme.PALE_INK,
                         anchor="w").pack(fill="x", pady=(5, 0))

    def _tiles(self, snap) -> None:
        row = ctk.CTkFrame(self.body, fg_color="transparent")
        row.pack(fill="x", pady=(0, 16))
        tiles = (
            ("Salary in", rand(snap.income), "One income, paid on the 1st", theme.GOOD),
            ("Total spent", rand(snap.total_spend),
             f"{pct(snap.spend_rate, 0)} of salary", theme.BLUE),
            ("Moved to savings", rand(snap.savings),
             f"{pct(snap.savings_rate)} of salary", theme.SKY),
            ("Closed at", rand(snap.closing_balance),
             "Opened at " + rand(snap.opening_balance),
             theme.GOOD if snap.closing_balance >= 0 else theme.BAD),
        )
        for index, (label, value, caption, accent) in enumerate(tiles):
            row.grid_columnconfigure(index, weight=1, uniform="tiles")
            StatTile(row, label, value, caption, accent).grid(
                row=0, column=index, sticky="nsew", padx=(0 if index == 0 else 8, 0))

    def _goals(self, snap) -> None:
        card = self.card("Where you stand", "Targets come from the rule book")
        holder = ctk.CTkFrame(card, fg_color="transparent")
        holder.pack(fill="x", padx=18, pady=(12, 18))

        ProgressRow(
            holder, "Savings goal",
            f"{rand(snap.savings)} of {rand(snap.savings_goal)}",
            snap.savings / snap.savings_goal if snap.savings_goal else 0,
            theme.SKY,
            "Rule: a healthy month moves 15% of salary into savings.",
        ).pack(fill="x", pady=(0, 14))

        ProgressRow(
            holder, "Salary used", f"{rand(snap.total_spend)} of {rand(snap.income)}",
            min(1.0, snap.spend_rate),
            theme.BAD if snap.spend_rate > 1 else theme.BLUE,
            "Rule: the bar fills at 100%. Past that, you are spending savings or credit.",
        ).pack(fill="x", pady=(0, 14))

        ProgressRow(
            holder, "Categories inside budget",
            f"{snap.categories_within_budget} of {len(self.insights.categories)}",
            snap.categories_within_budget / max(len(self.insights.categories), 1),
            theme.GOOD,
            "Rule: each category gets a fixed share of salary. See the Categories screen.",
        ).pack(fill="x")

    def _daily(self, snap) -> None:
        card = self.card("Spending, day by day",
                         f"{snap.no_spend_days} days without a single debit")
        chart = DailySpendChart(card)
        chart.pack(fill="x", padx=18, pady=(10, 6))
        days = sorted(snap.daily_spend.items())
        chart.bind("<Configure>", lambda event: chart.draw(days))

        peak_day, peak_amount = max(days, key=lambda item: item[1])
        note = ctk.CTkFrame(card, fg_color="transparent")
        note.pack(fill="x", padx=18, pady=(0, 16))
        self.text(note, f"Biggest day was {peak_day.strftime('%d %B')} at "
                        f"{rand(peak_amount)}, driven by "
                        f"{title(snap.biggest_purchase.narrative)}.",
                  size=theme.CAPTION, colour=theme.FAINT)


# ---------------------------------------------------------------------------
# 2. Categories
# ---------------------------------------------------------------------------

class CategoriesView(View):
    name = "Categories"
    blurb = "Every debit grouped by its statement category, as a share of salary."

    def build(self) -> None:
        self._split()
        self._budgets()

    def _split(self) -> None:
        card = self.card("Share of salary by category",
                         f"{len(self.insights.categories)} categories")
        holder = ctk.CTkFrame(card, fg_color="transparent")
        holder.pack(fill="x", padx=18, pady=(14, 18))

        donut = DonutChart(holder)
        donut.pack(side="left", padx=(0, 24))
        donut.draw(
            [(line.name, line.total, line.colour) for line in self.insights.categories],
            rand_short(self.insights.snapshot.total_spend), "total spend")

        legend = ctk.CTkFrame(holder, fg_color="transparent")
        legend.pack(side="left", fill="both", expand=True)
        for line in self.insights.categories:
            LegendRow(legend, line.name, line.colour, line.total,
                      line.share_of_income).pack(fill="x", pady=3)

    def _budgets(self) -> None:
        card = self.card("Running total against budget",
                         "Budget = a fixed share of salary")
        holder = ctk.CTkFrame(card, fg_color="transparent")
        holder.pack(fill="x", padx=18, pady=(12, 18))

        for line in self.insights.categories:
            accent = theme.STATUS_COLOURS[line.status]
            remaining = (f"{rand(line.remaining)} left" if line.remaining >= 0
                         else f"{rand(abs(line.remaining))} over")
            ProgressRow(
                holder, f"{line.name}  ({line.count} transactions)",
                f"{rand(line.total)} of {rand(line.budget)}",
                line.usage, accent,
                f"{theme.STATUS_WORDS[line.status]} - {remaining}",
            ).pack(fill="x", pady=(0, 13))


# ---------------------------------------------------------------------------
# 3. Merchants and rewards
# ---------------------------------------------------------------------------

class MerchantsView(View):
    name = "Merchants"
    blurb = ("Spend per store or service, with a Standard Bank UCount Rewards "
             "alternative for each one.")

    def build(self) -> None:
        merchants = self.insights.merchants
        report = self.insights.rewards_report

        banner = ctk.CTkFrame(self.body, fg_color=theme.NAVY, corner_radius=12)
        banner.pack(fill="x", pady=(0, 16))
        inner = ctk.CTkFrame(banner, fg_color="transparent")
        inner.pack(fill="x", padx=24, pady=20)
        ctk.CTkLabel(inner, text=f"{rand(report.current)} a month at your tier, "
                                 f"{rand(report.best)} at Tier 5",
                     font=theme.font(theme.TITLE, "bold"), text_color=theme.WHITE,
                     anchor="w").pack(fill="x")
        ctk.CTkLabel(inner, text="Every figure below is the published UCount earn rate "
                                 "for that merchant at your tiering level, applied to "
                                 "the share of the spend you could realistically move. "
                                 "See the Rewards screen for the tier ladder.",
                     font=theme.font(theme.BODY), text_color=theme.PALE_INK,
                     anchor="w", justify="left", wraplength=800).pack(fill="x",
                                                                      pady=(6, 0))

        card = self.card("Top ten by spend", "Debits only")
        chart = BarChart(card, rows=10, label_width=250)
        chart.pack(fill="x", padx=18, pady=(12, 14))
        rows = [(title(line.label), line.total,
                 theme.BLUE if index < 3 else theme.SKY)
                for index, line in enumerate(merchants[:10])]
        chart.bind("<Configure>", lambda event: chart.draw(rows))

        for line in merchants:
            self._merchant_card(line)

    def _merchant_card(self, line) -> None:
        card = self.card()
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=18, pady=(16, 6))
        ctk.CTkLabel(head, text=title(line.label), font=theme.font(theme.LEAD, "bold"),
                     text_color=theme.NAVY, anchor="w").pack(side="left")
        ctk.CTkLabel(head, text=rand(line.total), font=theme.font(theme.LEAD, "bold"),
                     text_color=theme.BLUE, anchor="e").pack(side="right")

        facts = ctk.CTkFrame(card, fg_color="transparent")
        facts.pack(fill="x", padx=18)
        summary = (f"{line.count} transaction{'s' if line.count != 1 else ''}, "
                   f"average {rand(line.average)}, {pct(line.share_of_income)} of "
                   f"salary, filed under {line.category}")
        self.text(facts, summary, size=theme.CAPTION, colour=theme.FAINT)

        tip = ctk.CTkFrame(card, fg_color=theme.WASH, corner_radius=8)
        tip.pack(fill="x", padx=18, pady=(12, 16))
        head_row = ctk.CTkFrame(tip, fg_color="transparent")
        head_row.pack(fill="x", padx=14, pady=(12, 2))
        ctk.CTkLabel(head_row, text=line.tip.partner,
                     font=theme.font(theme.BODY, "bold"), text_color=theme.BLUE_DARK,
                     anchor="w").pack(side="left")
        if line.estimate >= 1:
            Chip(head_row, f"{rand_short(line.estimate)} now, "
                           f"{rand_short(line.estimate_at(rewards.TIER_COUNT))} at Tier 5",
                 fill=theme.WHITE, text_colour=theme.GOOD).pack(side="right")

        body = ctk.CTkFrame(tip, fg_color="transparent")
        body.pack(fill="x", padx=14, pady=(0, 12))
        self.text(body, f"{line.tip.headline}  ({line.scheme.label})",
                  size=theme.CAPTION, colour=theme.MUTED, weight="bold")
        ctk.CTkLabel(body, text=line.tip.advice, font=theme.font(theme.BODY),
                     text_color=theme.INK, anchor="w", justify="left",
                     wraplength=720).pack(fill="x", pady=(4, 0))



# ---------------------------------------------------------------------------
# 4. UCount rewards tier
# ---------------------------------------------------------------------------

class RewardsView(View):
    name = "Rewards"
    blurb = ("Your UCount tiering level, scored off this statement, and what "
             "each level would pay back on the same spending.")

    def build(self) -> None:
        self._ladder()
        self._points()
        self._category()

    def _ladder(self) -> None:
        tiering = self.insights.tiering
        report = self.insights.rewards_report

        hero = ctk.CTkFrame(self.body, fg_color=theme.NAVY, corner_radius=14)
        hero.pack(fill="x", pady=(0, 16))
        inner = ctk.CTkFrame(hero, fg_color="transparent")
        inner.pack(fill="x", padx=26, pady=22)

        top = ctk.CTkFrame(inner, fg_color="transparent")
        top.pack(fill="x")
        ctk.CTkLabel(top, text=f"Tiering level {tiering.level}",
                     font=theme.font(theme.DISPLAY - 6, "bold"),
                     text_color=theme.WHITE, anchor="w").pack(side="left")
        Chip(top, f"{tiering.points} tiering points", fill=theme.NAVY_SOFT,
             text_colour=theme.WHITE).pack(side="right")

        gap = (f"{tiering.points_to_next} points short of level {tiering.level + 1}"
               if tiering.points_to_next else "Top level reached")
        ctk.CTkLabel(inner, text=f"{gap}. Your spending earns {rand(report.current)} "
                                 f"a month here, and would earn {rand(report.best)} "
                                 f"at Tier {rewards.TIER_COUNT}.",
                     font=theme.font(theme.BODY), text_color=theme.PALE_INK,
                     anchor="w", justify="left", wraplength=780).pack(fill="x",
                                                                      pady=(6, 12))

        bar = ctk.CTkProgressBar(inner, height=8, corner_radius=4,
                                 fg_color=theme.NAVY_SOFT, progress_color=theme.SKY)
        bar.set(min(1.0, tiering.points / rewards.TIER_THRESHOLDS[0][1]))
        bar.pack(fill="x")

        card = self.card("What the same spending earns at each level",
                         "Rewards points valued at one cent each")
        ladder = TierLadder(card)
        ladder.pack(fill="x", padx=18, pady=(14, 8))
        values, current = list(report.ladder), report.tier
        ladder.bind("<Configure>", lambda event: ladder.draw(values, current))

        note = ctk.CTkFrame(card, fg_color="transparent")
        note.pack(fill="x", padx=18, pady=(0, 16))
        self.text(note,
                  f"These are credit card rates. The same spending on the "
                  f"debit card attached to this account earns "
                  f"{rand(report.debit_at_current)} a month at your tier, which is "
                  f"the single biggest reason to move everyday purchases across.",
                  size=theme.CAPTION, colour=theme.FAINT, wraplength=800)

    def _points(self) -> None:
        tiering = self.insights.tiering
        card = self.card("Where your tiering points come from",
                         f"{tiering.available} points still available")
        holder = ctk.CTkFrame(card, fg_color="transparent")
        holder.pack(fill="x", padx=18, pady=(12, 18))

        for line in tiering.lines:
            share = line.points / line.rule.cap if line.rule.cap else 0
            accent = (theme.GOOD if share >= 0.99 else
                      theme.BLUE if share > 0 else theme.WARN)
            note = line.evidence
            if line.headroom and line.rule.action:
                note = f"{line.evidence}. {line.rule.action}"
            ProgressRow(
                holder, f"{line.rule.name}  ({line.rule.code})",
                f"{line.points} of {line.rule.cap} points",
                share, accent, note,
            ).pack(fill="x", pady=(0, 13))

    def _category(self) -> None:
        report = self.insights.rewards_report
        card = self.card("Choose your own rewards",
                         "One category only, so pick the biggest")
        holder = ctk.CTkFrame(card, fg_color="transparent")
        holder.pack(fill="x", padx=18, pady=(12, 8))

        label = rewards.CYOR_FAMILY_LABELS.get(report.cyor_family,
                                               report.cyor_family.title())
        ctk.CTkLabel(holder, text=f"{label} is your best pick",
                     font=theme.font(theme.LEAD, "bold"), text_color=theme.BLUE_DARK,
                     anchor="w").pack(fill="x")
        self.text(holder,
                  f"You spent {rand(report.cyor_spend)} in that category this month, "
                  f"more than in fashion or lifestyle. Only the chosen category earns "
                  f"the boosted rate; the rest of your spending drops to the plain "
                  f"card rate.",
                  size=theme.BODY, colour=theme.INK, wraplength=800)
        self.text(holder,
                  f"The boosted rate is capped at the lower of 20% of card spend or "
                  f"R3 000 in the chosen category each cycle, and fuel is capped at "
                  f"R2 500. Those caps are applied in every figure on this screen.",
                  size=theme.CAPTION, colour=theme.FAINT, wraplength=800)
        holder.pack_configure(pady=(12, 18))


# ---------------------------------------------------------------------------
# 5. Security
# ---------------------------------------------------------------------------

class SecurityView(View):
    name = "Security"
    blurb = ("Six fraud checks run over every transaction. Two or more hits means "
             "escalation.")

    def build(self) -> None:
        self._escalations()
        self._monitor()
        self._settlement()

    def _escalations(self) -> None:
        escalations = self.insights.escalations
        card = self.card("Escalated to the Fraud department",
                         f"{len(escalations)} transaction(s)")
        if not escalations:
            holder = ctk.CTkFrame(card, fg_color="transparent")
            holder.pack(fill="x", padx=18, pady=(10, 16))
            self.text(holder, "No transaction triggered two or more checks.",
                      colour=theme.GOOD)
            return
        for index, finding in enumerate(escalations):
            self._finding(card, finding, theme.BAD,
                          last=index == len(escalations) - 1)

    def _monitor(self) -> None:
        watch = [f for f in self.insights.fraud if not f.escalate]
        card = self.card("Worth a second look", "One check triggered, not enough to escalate")
        if not watch:
            holder = ctk.CTkFrame(card, fg_color="transparent")
            holder.pack(fill="x", padx=18, pady=(10, 16))
            self.text(holder, "Nothing else triggered a check.", colour=theme.FAINT)
            return
        for index, finding in enumerate(watch):
            self._finding(card, finding, theme.WARN,
                          last=index == len(watch) - 1)

    def _finding(self, card, finding, accent: str, last: bool = False) -> None:
        holder = ctk.CTkFrame(card, fg_color=theme.WHITE)
        holder.pack(fill="x", padx=18, pady=(14, 18 if last else 0))

        strip = ctk.CTkFrame(holder, fg_color="transparent")
        strip.pack(fill="x")
        rule = ctk.CTkFrame(strip, fg_color=accent, width=4, corner_radius=2)
        rule.pack(side="left", fill="y", padx=(0, 12))

        detail = ctk.CTkFrame(strip, fg_color="transparent")
        detail.pack(side="left", fill="both", expand=True)

        top = ctk.CTkFrame(detail, fg_color="transparent")
        top.pack(fill="x")
        ctk.CTkLabel(top, text=title(finding.txn.narrative),
                     font=theme.font(theme.BODY, "bold"), text_color=theme.NAVY,
                     anchor="w", wraplength=540, justify="left").pack(side="left")
        ctk.CTkLabel(top, text=rand(finding.txn.outflow),
                     font=theme.font(theme.LEAD, "bold"), text_color=accent,
                     anchor="e").pack(side="right")

        txn = finding.txn
        self.text(detail,
                  f"{txn.txn_id} ({txn.reference}) on "
                  f"{txn.transaction_date.strftime('%d %B %Y at %H:%M')}, leaving a "
                  f"balance of {rand(txn.running_balance)}",
                  size=theme.CAPTION, colour=theme.FAINT)

        Chip(detail, finding.verdict, fill=accent,
             text_colour=theme.WHITE).pack(anchor="w", pady=(8, 6))

        for hit in finding.hits:
            row = ctk.CTkFrame(detail, fg_color="transparent")
            row.pack(fill="x", pady=1)
            Chip(row, hit.code).pack(side="left", padx=(0, 8))
            ctk.CTkLabel(row, text=f"{hit.title} — {hit.reason}",
                         font=theme.font(theme.CAPTION), text_color=theme.MUTED,
                         anchor="w", wraplength=640, justify="left").pack(side="left")

        if txn.disclaimer:
            self.text(detail, f"Bank note: {txn.disclaimer}", size=theme.CAPTION,
                      colour=theme.FAINT)
        if not last:
            ctk.CTkFrame(detail, fg_color=theme.BORDER,
                         height=1).pack(fill="x", pady=(14, 0))

    def _settlement(self) -> None:
        settlements = self.insights.settlements
        late = self.insights.late_settlements
        card = self.card("Did it reflect within 24 hours?",
                         f"Service level: {SETTLEMENT_SLA_HOURS:.0f} hours")

        holder = ctk.CTkFrame(card, fg_color="transparent")
        holder.pack(fill="x", padx=18, pady=(12, 6))
        verdict = ("Every transaction posted inside the 24 hour window."
                   if not late else f"{len(late)} transaction(s) posted late.")
        self.text(holder, verdict, colour=theme.GOOD if not late else theme.BAD,
                  weight="bold")

        refunds = [line for line in settlements
                   if line.txn.category == "Refund / Reversal"]
        if refunds:
            self.text(holder, "Refunds and reversals", size=theme.CAPTION,
                      colour=theme.MUTED, weight="bold")
            for line in refunds:
                self._settlement_row(holder, line, highlight=True)

        self.text(holder, "Slowest to post", size=theme.CAPTION,
                  colour=theme.MUTED, weight="bold")
        for line in settlements[:6]:
            self._settlement_row(holder, line)
        holder.pack_configure(pady=(12, 18))

    def _settlement_row(self, master, line, highlight: bool = False) -> None:
        row = ctk.CTkFrame(master, fg_color=theme.WASH if highlight else "transparent",
                           corner_radius=6)
        row.pack(fill="x", pady=2)
        inner = ctk.CTkFrame(row, fg_color="transparent")
        inner.pack(fill="x", padx=10, pady=6)
        ctk.CTkLabel(inner, text=title(line.txn.narrative),
                     font=theme.font(theme.BODY), text_color=theme.INK,
                     anchor="w").pack(side="left")
        mark = "within 24 hours" if line.within_sla else "outside 24 hours"
        ctk.CTkLabel(inner, text=mark, font=theme.font(theme.CAPTION),
                     text_color=theme.GOOD if line.within_sla else theme.BAD,
                     width=120, anchor="e").pack(side="right")
        ctk.CTkLabel(inner, text=hours(line.lag_hours), font=theme.font(theme.BODY, "bold"),
                     text_color=theme.NAVY, width=80, anchor="e").pack(side="right")


# ---------------------------------------------------------------------------
# 5. Quests
# ---------------------------------------------------------------------------

class QuestsView(View):
    name = "Quests"
    blurb = "Missions for next month, badges earned so far, and how the score is built."

    def build(self) -> None:
        self._challenges()
        self._badges()
        self._score()

    def _challenges(self) -> None:
        card = self.card("Missions for next month", "Complete one to earn XP")
        holder = ctk.CTkFrame(card, fg_color="transparent")
        holder.pack(fill="x", padx=18, pady=(12, 18))
        for challenge, progress, status in self.insights.challenges:
            done = progress >= 1.0
            accent = theme.GOOD if done else theme.BLUE
            ProgressRow(
                holder, f"{challenge.name}   +{challenge.xp} XP",
                "Complete" if done else f"{progress * 100:.0f}%",
                progress, accent, f"{challenge.goal} — {status}",
            ).pack(fill="x", pady=(0, 14))

    def _badges(self) -> None:
        earned = sum(1 for _, ok in self.insights.badges if ok)
        card = self.card("Badges", f"{earned} of {len(self.insights.badges)} earned")
        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(fill="x", padx=18, pady=(12, 18))
        for column in range(3):
            grid.grid_columnconfigure(column, weight=1, uniform="badges")

        for index, (badge, ok) in enumerate(self.insights.badges):
            tile = ctk.CTkFrame(grid, fg_color=theme.WASH if ok else theme.WHITE,
                                corner_radius=10, border_width=1,
                                border_color=theme.BORDER)
            tile.grid(row=index // 3, column=index % 3, sticky="nsew",
                      padx=(0 if index % 3 == 0 else 10, 0), pady=(0, 10))
            inner = ctk.CTkFrame(tile, fg_color="transparent")
            inner.pack(fill="both", expand=True, padx=14, pady=12)
            ctk.CTkLabel(inner, text=badge.name,
                         font=theme.font(theme.BODY, "bold"),
                         text_color=theme.NAVY if ok else theme.FAINT,
                         anchor="w").pack(fill="x")
            ctk.CTkLabel(inner, text=badge.requirement,
                         font=theme.font(theme.CAPTION),
                         text_color=theme.MUTED if ok else theme.FAINT,
                         anchor="w", justify="left", wraplength=190).pack(fill="x",
                                                                          pady=(3, 6))
            Chip(inner, "Earned" if ok else "Locked",
                 fill=theme.GOOD if ok else theme.WASH,
                 text_colour=theme.WHITE if ok else theme.FAINT).pack(anchor="w")

    def _score(self) -> None:
        card = self.card(f"How the {self.insights.score:.0f} was calculated",
                         f"Six components, 100 points, {self.insights.health_level} level")
        holder = ctk.CTkFrame(card, fg_color="transparent")
        holder.pack(fill="x", padx=18, pady=(12, 18))
        for line in self.insights.score_lines:
            share = line.points / line.max_points if line.max_points else 0
            accent = theme.GOOD if share >= 0.8 else theme.WARN if share >= 0.4 else theme.BAD
            ProgressRow(
                holder, line.name, f"{line.points:g} of {line.max_points:g} points",
                share, accent, line.rule_text,
            ).pack(fill="x", pady=(0, 13))



# ---------------------------------------------------------------------------
# 6. Balance notifications
# ---------------------------------------------------------------------------

class AlertsView(View):
    name = "Alerts"
    blurb = ("Notifications fire as you spend down the month's available funds, "
             "and get louder as the balance drops.")

    def build(self) -> None:
        self._meter()
        self._timeline()
        self._offer()

    def _meter(self) -> None:
        snap = self.insights.snapshot
        card = self.card("Funds used this month",
                         f"Available funds = {AVAILABLE_FUNDS_RULE}")
        holder = ctk.CTkFrame(card, fg_color="transparent")
        holder.pack(fill="x", padx=18, pady=(14, 10))

        summary = ctk.CTkFrame(holder, fg_color="transparent")
        summary.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(summary,
                     text=f"{rand(snap.total_spend)} of {rand(snap.available_funds)}",
                     font=theme.font(theme.TITLE, "bold"), text_color=theme.NAVY,
                     anchor="w").pack(side="left")
        level = self.insights.alert_level
        if level != "none":
            Chip(summary, LEVEL_WORDS[level], fill=LEVEL_COLOURS[level],
                 text_colour=theme.WHITE).pack(side="right")

        meter = ThresholdMeter(holder)
        meter.pack(fill="x")
        reached = {alert.rule.threshold for alert in self.insights.alerts}
        marks = [(alert_rule.threshold, LEVEL_COLOURS[alert_rule.level],
                  alert_rule.threshold in reached)
                 for alert_rule in sorted(ALERT_RULES, key=lambda r: r.threshold)]
        fraction = snap.funds_used
        colour = theme.BAD if fraction >= 0.90 else theme.BLUE
        meter.bind("<Configure>", lambda event: meter.draw(fraction, marks, colour))

        note = ctk.CTkFrame(card, fg_color="transparent")
        note.pack(fill="x", padx=18, pady=(0, 16))
        self.text(note,
                  f"All four notifications fired this month. Spending finished at "
                  f"{pct(fraction, 0)} of available funds."
                  if len(self.insights.alerts) == len(ALERT_RULES) else
                  f"{len(self.insights.alerts)} of {len(ALERT_RULES)} notifications "
                  f"fired this month.",
                  size=theme.CAPTION, colour=theme.FAINT)

    def _timeline(self) -> None:
        card = self.card("What the customer received",
                         f"{len(self.insights.alerts)} notifications")
        if not self.insights.alerts:
            holder = ctk.CTkFrame(card, fg_color="transparent")
            holder.pack(fill="x", padx=18, pady=(10, 16))
            self.text(holder, "Spending stayed below every threshold this month.",
                      colour=theme.GOOD)
            return

        for index, alert in enumerate(self.insights.alerts):
            last = index == len(self.insights.alerts) - 1
            self._alert(card, alert, last)

    def _alert(self, card, alert, last: bool) -> None:
        accent = LEVEL_COLOURS[alert.rule.level]
        holder = ctk.CTkFrame(card, fg_color="transparent")
        holder.pack(fill="x", padx=18, pady=(14, 18 if last else 0))

        rule = ctk.CTkFrame(holder, fg_color=accent, width=4, height=1,
                            corner_radius=2)
        rule.pack(side="left", fill="y", padx=(0, 12))
        detail = ctk.CTkFrame(holder, fg_color="transparent")
        detail.pack(side="left", fill="both", expand=True)

        top = ctk.CTkFrame(detail, fg_color="transparent")
        top.pack(fill="x")
        ctk.CTkLabel(top, text=alert.rule.title,
                     font=theme.font(theme.LEAD, "bold"), text_color=theme.NAVY,
                     anchor="w").pack(side="left")
        Chip(top, f"{alert.rule.threshold:.0%} used", fill=accent,
             text_colour=theme.WHITE).pack(side="right")

        ctk.CTkLabel(detail, text=alert.message, font=theme.font(theme.BODY),
                     text_color=theme.INK, anchor="w", justify="left",
                     wraplength=700).pack(fill="x", pady=(6, 4))
        if alert.rule.action:
            self.text(detail, alert.rule.action, size=theme.BODY,
                      colour=accent, weight="bold")
        self.text(detail,
                  f"Sent on {alert.txn.transaction_date.strftime('%d %B at %H:%M')}, "
                  f"triggered by {title(alert.txn.narrative)} "
                  f"({rand(alert.txn.outflow)})",
                  size=theme.CAPTION, colour=theme.FAINT)
        if not last:
            ctk.CTkFrame(detail, fg_color=theme.BORDER,
                         height=1).pack(fill="x", pady=(14, 0))

    def _offer(self) -> None:
        offer = self.insights.credit_offer
        if not offer.triggered:
            return

        card = self.card("Credit card option",
                         f"{offer.passed} of {len(offer.checks)} checks passed")
        holder = ctk.CTkFrame(card, fg_color="transparent")
        holder.pack(fill="x", padx=18, pady=(12, 8))

        verdict = theme.GOOD if offer.prequalified else theme.WARN
        ctk.CTkLabel(holder, text=offer.outcome,
                     font=theme.font(theme.LEAD, "bold"), text_color=verdict,
                     anchor="w", justify="left", wraplength=700).pack(fill="x")
        self.text(holder,
                  f"Rule: a pre-qualified offer needs {CREDIT_PREQUALIFY_MIN} of the "
                  f"{len(offer.checks)} checks below. Indicative limit is one month "
                  f"of disposable income, being salary less commitments, groceries "
                  f"and transport, rounded down to the nearest R500.",
                  size=theme.CAPTION, colour=theme.MUTED, wraplength=760)

        for check, ok in offer.checks:
            row = ctk.CTkFrame(holder, fg_color="transparent")
            row.pack(fill="x", pady=3)
            Chip(row, "Pass" if ok else "Not met",
                 fill=theme.GOOD if ok else theme.WASH,
                 text_colour=theme.WHITE if ok else theme.FAINT).pack(side="left",
                                                                      padx=(0, 10))
            ctk.CTkLabel(row, text=f"{check.name} — {check.requirement}",
                         font=theme.font(theme.CAPTION), text_color=theme.MUTED,
                         anchor="w", wraplength=620, justify="left").pack(side="left")

        limit_box = ctk.CTkFrame(card, fg_color=theme.WASH, corner_radius=8)
        limit_box.pack(fill="x", padx=18, pady=(12, 8))
        inner = ctk.CTkFrame(limit_box, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=12)
        ctk.CTkLabel(inner, text=f"Indicative limit {rand(offer.limit, 0)}",
                     font=theme.font(theme.LEAD, "bold"), text_color=theme.BLUE_DARK,
                     anchor="w").pack(fill="x")
        ctk.CTkLabel(inner, text=CREDIT_DISCLAIMER, font=theme.font(theme.CAPTION),
                     text_color=theme.MUTED, anchor="w", justify="left",
                     wraplength=700).pack(fill="x", pady=(4, 0))
        limit_box.pack_configure(pady=(12, 18))


# ---------------------------------------------------------------------------
# 7. Transactions
# ---------------------------------------------------------------------------

class TransactionsView(View):
    name = "Transactions"
    blurb = "The full statement, filterable by category."

    HEADINGS = {"date": "Date", "narrative": "Narrative", "category": "Category",
                "type": "Type", "amount": "Amount", "balance": "Balance"}
    KEYS = ("date", "narrative", "category", "type", "amount", "balance")
    NARRATIVE_LIMIT = 26

    def build(self) -> None:
        categories = ["All categories"] + sorted(
            {txn.category for txn in self.insights.statement.transactions})

        card = self.card("Statement", f"{len(self.insights.statement)} transactions")
        controls = ctk.CTkFrame(card, fg_color="transparent")
        controls.pack(fill="x", padx=18, pady=(12, 6))

        self.filter = ctk.CTkComboBox(
            controls, values=categories, width=260, height=32,
            font=theme.font(theme.BODY), border_color=theme.BORDER,
            button_color=theme.BLUE, button_hover_color=theme.BLUE_DARK,
            fg_color=theme.WHITE, text_color=theme.INK, state="readonly",
            command=lambda _choice: self.refresh())
        self.filter.set("All categories")
        self.filter.pack(side="left")

        self.count_label = ctk.CTkLabel(controls, text="", font=theme.font(theme.CAPTION),
                                        text_color=theme.MUTED)
        self.count_label.pack(side="right")

        self._style_table()
        wrapper = ctk.CTkFrame(card, fg_color=theme.WHITE)
        wrapper.pack(fill="both", expand=True, padx=18, pady=(10, 18))

        self.table = ttk.Treeview(wrapper, columns=self.KEYS, show="headings",
                                  height=22, style="BQ.Treeview")
        for key, width in self._column_widths().items():
            self.table.heading(key, text=self.HEADINGS[key])
            self.table.column(key, width=width, minwidth=60,
                              stretch=(key == "narrative"),
                              anchor="e" if key in ("amount", "balance") else "w")
        scrollbar = ttk.Scrollbar(wrapper, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scrollbar.set)
        self.table.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.table.tag_configure("credit", foreground=theme.GOOD)
        self.table.tag_configure("flagged", background="#FDECEC")
        self.refresh()

    def _column_widths(self) -> dict[str, int]:
        """Size each column to its widest real value, measured in the actual font."""
        from tkinter import font as tkfont

        metric = tkfont.Font(font=theme.font(theme.BODY))
        widest = {key: metric.measure(self.HEADINGS[key]) for key in self.KEYS}
        for txn in self.insights.statement.transactions:
            for key, value in zip(self.KEYS, self._row(txn)):
                widest[key] = max(widest[key], metric.measure(value))
        return {key: value + 18 for key, value in widest.items()}

    def _row(self, txn) -> tuple[str, ...]:
        """One statement row, formatted. Used for both sizing and display."""
        return (txn.transaction_date.strftime("%d %b %H:%M"),
                shorten(title(txn.narrative), self.NARRATIVE_LIMIT),
                txn.category, txn.txn_type.title(),
                rand(txn.amount), rand(txn.running_balance))

    def _style_table(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("BQ.Treeview", background=theme.WHITE,
                        fieldbackground=theme.WHITE, foreground=theme.INK,
                        rowheight=27, borderwidth=0, font=theme.font(theme.BODY))
        style.configure("BQ.Treeview.Heading", background=theme.WASH,
                        foreground=theme.NAVY, relief="flat",
                        font=theme.font(theme.CAPTION, "bold"))
        style.map("BQ.Treeview", background=[("selected", theme.SKY)],
                  foreground=[("selected", theme.WHITE)])

    def refresh(self) -> None:
        chosen = self.filter.get()
        flagged = {finding.txn.txn_id for finding in self.insights.escalations}
        self.table.delete(*self.table.get_children())

        shown = 0
        for txn in self.insights.statement.transactions:
            if chosen != "All categories" and txn.category != chosen:
                continue
            tags = []
            if txn.is_credit:
                tags.append("credit")
            if txn.txn_id in flagged:
                tags.append("flagged")
            self.table.insert("", "end", tags=tuple(tags), values=self._row(txn))
            shown += 1
        self.count_label.configure(text=f"Showing {shown} of "
                                        f"{len(self.insights.statement)}")


#: Navigation order. Append a class here to add a screen.
VIEWS: tuple[type[View], ...] = (
    DashboardView, CategoriesView, MerchantsView, RewardsView,
    SecurityView, AlertsView, QuestsView, TransactionsView,
)
