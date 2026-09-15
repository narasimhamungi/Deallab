"""
Deal terms: what the buyer agreed to pay, in the form it agreed to pay it.

The reason this is its own module rather than three fields on a config object is the
contingent consideration. Most merger-model templates handle "cash per share" and
"stock exchange ratio" and stop. Real deals -- especially medtech and biotech, where
the disputed value sits in a clinical or commercial milestone nobody can price at
signing -- routinely carry a CVR. J&J/Abiomed is exactly this shape: $380.00 in cash
up front plus a non-tradeable CVR worth up to $35.00 per share on three separate
milestones.

A CVR is not a rounding detail. $35.00 on top of $380.00 is 9.2% of the headline price.
Ignoring it understates the price paid; booking it at its $35.00 maximum overstates it
by assuming every milestone hits. Under ASC 805 contingent consideration is recognised
at acquisition-date fair value and remeasured through earnings thereafter -- so the
honest treatment is a probability-weighted value, tagged ASSUMED, with the probability
visible in the assumption register where a reviewer can attack it.

Deliberately NOT modelled here: the remeasurement path. Post-close mark-to-market of
the CVR liability runs through the buyer's P&L and would affect reported (not adjusted)
EPS in later years. That is a real effect and it is out of scope -- stated rather than
silently omitted.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .provenance import AssumptionRegister, Input


class Consideration(Enum):
    ALL_CASH = "all_cash"
    ALL_STOCK = "all_stock"
    MIXED = "mixed"


@dataclass(frozen=True)
class ContingentValueRight:
    """A CVR attached to the consideration.

    `max_per_share` is sourced from the merger agreement. `probability_weight` is the
    analyst's estimate of the expected fraction of the maximum that will be paid, and
    it is the number a reviewer should attack first.
    """
    max_per_share: Input
    probability_weight: Input  # 0.0-1.0 of the maximum expected to be earned
    milestones: str            # plain-English description, quoted from the agreement
    tradeable: bool = False

    def expected_per_share(self) -> float:
        w = self.probability_weight.required()
        if not 0.0 <= w <= 1.0:
            raise ValueError(
                f"CVR probability weight must be in [0,1], got {w}. This is a fraction "
                f"of the maximum payout, not a dollar figure.")
        return self.max_per_share.required() * w


@dataclass(frozen=True)
class DealTerms:
    """The consideration structure as agreed, before any financing decision.

    Separating terms from financing is deliberate. What the buyer pays the seller and
    how the buyer funds that payment are independent choices, and conflating them is
    how merger models end up unable to answer "would this still be accretive if it were
    equity-funded?" -- which is the question that actually distinguishes a good deal
    from cheap money.
    """
    acquirer: str
    target: str
    announced: str                    # ISO date
    closed: str | None                # ISO date, None if pending/terminated
    consideration_type: Consideration
    cash_per_share: Input
    target_shares_outstanding: Input  # fully diluted, in millions
    target_net_debt: Input            # in USD millions; negative = net cash
    stated_enterprise_value: Input    # what the buyer's release said the EV was
    cvr: ContingentValueRight | None = None
    exchange_ratio: Input | None = None     # acquirer shares per target share
    acquirer_share_price_at_announce: Input | None = None
    target_share_price_unaffected: Input | None = None  # last close before leak/announce
    source: str = ""

    # --- Consideration arithmetic -------------------------------------------------

    def upfront_equity_purchase_price(self) -> float:
        """Cash + stock paid to target shareholders at close, excluding contingent."""
        shares = self.target_shares_outstanding.required()
        total = self.cash_per_share.required() * shares
        if self.exchange_ratio is not None and self.acquirer_share_price_at_announce is not None:
            total += (self.exchange_ratio.required()
                      * self.acquirer_share_price_at_announce.required() * shares)
        return total

    def contingent_consideration_fair_value(self) -> float:
        """Probability-weighted CVR value at acquisition date. Zero if no CVR."""
        if self.cvr is None:
            return 0.0
        return self.cvr.expected_per_share() * self.target_shares_outstanding.required()

    def total_equity_purchase_price(self) -> float:
        return self.upfront_equity_purchase_price() + self.contingent_consideration_fair_value()

    def implied_enterprise_value(self) -> float:
        """EV derived from the consideration, independent of whatever the press release
        claimed. The two are then compared -- see `ev_reconciliation`."""
        return self.total_equity_purchase_price() + self.target_net_debt.required()

    def ev_reconciliation(self) -> str:
        """Derived EV vs. the buyer's stated EV.

        These rarely tie exactly, and the gap is informative rather than an error:
        press-release EV figures are often struck at a different date, may or may not
        include the CVR, and 'enterprise value including cash acquired' (J&J's own
        phrasing on Abiomed) is not standard EV language at all. Reporting the gap is
        the point; silently adopting the press-release number would discard a real
        check on whether the share count and net debt used here are right.
        """
        derived = self.implied_enterprise_value()
        stated = self.stated_enterprise_value.value
        if stated is None:
            return "No stated EV supplied -- derived EV stands alone, unchecked."
        gap = derived - stated
        gap_pct = gap / stated if stated else float("inf")
        verdict = "ties" if abs(gap_pct) < 0.02 else "DIVERGES"
        return (f"Derived EV ${derived:,.0f}mm vs. stated ${stated:,.0f}mm: "
                f"{gap:+,.0f}mm ({gap_pct:+.1%}) -- {verdict}. "
                f"Derived EV includes contingent consideration at fair value "
                f"(${self.contingent_consideration_fair_value():,.0f}mm); a stated EV "
                f"usually does not.")

    def premium_to_unaffected(self) -> float | None:
        """Upfront cash premium over the last unaffected target share price.

        Uses upfront consideration only, not the CVR -- a premium quoted inclusive of a
        contingent payout is not a premium, it is a maximum.
        """
        if self.target_share_price_unaffected is None or self.target_share_price_unaffected.is_missing:
            return None
        unaffected = self.target_share_price_unaffected.required()
        return self.cash_per_share.required() / unaffected - 1.0

    def register(self, reg: AssumptionRegister) -> None:
        reg.record(self.cash_per_share, self.target_shares_outstanding,
                   self.target_net_debt, self.stated_enterprise_value)
        if self.cvr is not None:
            reg.record(self.cvr.max_per_share, self.cvr.probability_weight)
        for optional in (self.exchange_ratio, self.acquirer_share_price_at_announce,
                         self.target_share_price_unaffected):
            if optional is not None:
                reg.record(optional)
