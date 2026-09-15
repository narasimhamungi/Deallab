"""
How the buyer funds the purchase price, and what that funding costs.

The single most common way a merger model flatters a deal is by funding it with
balance-sheet cash and forgetting that the cash was earning something. Cash used for an
acquisition stops earning interest income; that foregone income is a real charge against
pro-forma EPS and it is invisible unless the model explicitly books it. In a low-rate
era the omission was small. At 2022-2026 short rates on a multi-billion cash drawdown it
is worth cents of EPS -- enough on its own to flip a marginal deal from accretive to
dilutive.

The second most common flattery is treating all new debt as one blended tranche at one
rate. Real acquisition financing is layered: commercial paper or a bridge at short
rates, then a term takeout across a maturity curve. Modelling it as a single rate is
usually fine for the first year and increasingly wrong after, because the bridge is
repaid and the cost mix changes. Tranches are supported here; using one is allowed but
is a choice, not a default that hides itself.

What this module does NOT do: optimise the structure. It prices the structure you give
it. A module that searched for the financing mix that maximised accretion would be
building the case for a predetermined answer, which is the opposite of the job.
"""

from __future__ import annotations

from dataclasses import dataclass

from .provenance import AssumptionRegister, Input


@dataclass(frozen=True)
class DebtTranche:
    """One layer of acquisition financing."""
    label: str
    principal: Input          # USD millions
    rate: Input               # annual pre-tax coupon/all-in rate, decimal
    tenor_years: Input | None = None
    amortising: bool = False  # True = straight-line principal repayment over tenor
    issuance_fee_pct: Input | None = None  # of principal, capitalised not expensed

    def interest_expense(self, year_index: int) -> float:
        """Pre-tax interest in a given forward year (1 = first full year post-close).

        Amortising tranches pay interest on the average balance for the year, which is
        the convention that matches how a term loan actually accrues -- using the
        opening balance overstates interest, using the closing balance understates it.
        """
        principal = self.principal.required()
        if not self.amortising or self.tenor_years is None:
            return principal * self.rate.required()
        tenor = self.tenor_years.required()
        if year_index > tenor:
            return 0.0
        repay_per_year = principal / tenor
        opening = principal - repay_per_year * (year_index - 1)
        closing = max(opening - repay_per_year, 0.0)
        return (opening + closing) / 2.0 * self.rate.required()

    def balance(self, year_index: int) -> float:
        principal = self.principal.required()
        if not self.amortising or self.tenor_years is None:
            return principal
        tenor = self.tenor_years.required()
        return max(principal - (principal / tenor) * year_index, 0.0)

    def issuance_fees(self) -> float:
        if self.issuance_fee_pct is None or self.issuance_fee_pct.is_missing:
            return 0.0
        return self.principal.required() * self.issuance_fee_pct.required()


@dataclass(frozen=True)
class FinancingPlan:
    """The full funding stack for one transaction.

    `cash_on_hand_used` is the buyer's own balance-sheet cash. `foregone_yield` is what
    that cash was earning -- supply it or the model will tell you it is missing rather
    than assume zero, because assuming zero is a silent subsidy to the deal.
    """
    cash_on_hand_used: Input
    foregone_yield: Input              # pre-tax annual yield on the cash given up
    tranches: tuple[DebtTranche, ...] = ()
    new_equity_issued: Input | None = None       # USD millions raised
    new_equity_price: Input | None = None        # issue price per share
    advisory_fees: Input | None = None           # expensed, not capitalised (ASC 805)
    other_transaction_costs: Input | None = None

    # --- Totals -------------------------------------------------------------------

    def total_new_debt(self) -> float:
        return sum(t.principal.required() for t in self.tranches)

    def total_issuance_fees(self) -> float:
        return sum(t.issuance_fees() for t in self.tranches)

    def expensed_transaction_costs(self) -> float:
        """Advisory/legal/other, expensed as incurred under ASC 805-10-25-23.

        These are NOT part of the consideration transferred and do not enter goodwill.
        Merger models that add banker fees to the purchase price and amortise them are
        making an error that a technical interviewer will catch in one question.
        """
        total = 0.0
        for f in (self.advisory_fees, self.other_transaction_costs):
            if f is not None and not f.is_missing:
                total += f.required()
        return total

    def new_shares_issued(self) -> float:
        if self.new_equity_issued is None or self.new_equity_issued.is_missing:
            return 0.0
        if self.new_equity_price is None or self.new_equity_price.is_missing:
            raise ValueError(
                "new_equity_issued supplied without new_equity_price -- cannot derive "
                "the share count, and the share count is what drives dilution.")
        return self.new_equity_issued.required() / self.new_equity_price.required()

    def total_funding(self) -> float:
        equity = (self.new_equity_issued.required()
                  if self.new_equity_issued is not None and not self.new_equity_issued.is_missing
                  else 0.0)
        return self.cash_on_hand_used.required() + self.total_new_debt() + equity

    # --- Annual cost --------------------------------------------------------------

    def interest_expense(self, year_index: int) -> float:
        return sum(t.interest_expense(year_index) for t in self.tranches)

    def foregone_interest_income(self) -> float:
        """The charge nobody books. Pre-tax."""
        return self.cash_on_hand_used.required() * self.foregone_yield.required()

    def pretax_financing_cost(self, year_index: int) -> float:
        return self.interest_expense(year_index) + self.foregone_interest_income()

    def debt_balance(self, year_index: int) -> float:
        return sum(t.balance(year_index) for t in self.tranches)

    def describe(self) -> str:
        lines = [(f"Cash on hand:        ${self.cash_on_hand_used.required():>10,.0f}mm "
                  f"(foregone yield {self.foregone_yield.required():.2%} -> "
                  f"${self.foregone_interest_income():,.0f}mm/yr pre-tax)")]
        for t in self.tranches:
            amort = f", {t.tenor_years.required():.0f}yr amortising" if t.amortising and t.tenor_years else ""
            lines.append(f"{t.label + ':':<21}${t.principal.required():>10,.0f}mm "
                         f"@ {t.rate.required():.2%}{amort}")
        if self.new_equity_issued is not None and not self.new_equity_issued.is_missing:
            lines.append(f"New equity:          ${self.new_equity_issued.required():>10,.0f}mm "
                         f"({self.new_shares_issued():,.1f}mm shares)")
        lines.append(f"{'Total funding:':<21}${self.total_funding():>10,.0f}mm")
        return "\n".join(lines)

    def register(self, reg: AssumptionRegister) -> None:
        reg.record(self.cash_on_hand_used, self.foregone_yield)
        for t in self.tranches:
            reg.record(t.principal, t.rate)
            for opt in (t.tenor_years, t.issuance_fee_pct):
                if opt is not None:
                    reg.record(opt)
        for opt in (self.new_equity_issued, self.new_equity_price,
                    self.advisory_fees, self.other_transaction_costs):
            if opt is not None:
                reg.record(opt)
