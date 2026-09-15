"""
Pro-forma combination, presented as a bridge rather than a stack.

Two income statements added together tells you almost nothing. What a reviewer needs to
see is the walk: buyer standalone net income, plus the target's contribution, plus
synergies, minus financing cost, minus purchase accounting -- arriving at pro-forma net
income with every step labelled and signed. If the deal is dilutive, the bridge names
the line that made it dilutive. That is the output, not the total.

GAAP and adjusted are computed in the same pass and kept as separate fields. They differ
by exactly the items buyers exclude from adjusted earnings: intangible amortisation
arising from the transaction, the inventory step-up unwind, and one-time integration
cost. Nothing else is excluded here -- adjusted EPS becomes meaningless the moment the
exclusion list is a matter of taste, and the point of computing both is to show the size
of the gap, not to pick a favourite.

One asymmetry deliberately preserved: financing cost is in BOTH figures. Buyers exclude
amortisation from adjusted EPS; they do not exclude the interest on the debt they raised
to buy the thing. J&J's own Abiomed guidance said "slightly dilutive to neutral to
adjusted earnings per share in the first year, **considering the impact of financing**"
-- financing drag inside an adjusted number is the disclosed treatment, and matching it
is what makes this model checkable against the guidance.
"""

from __future__ import annotations

from dataclasses import dataclass

from .financing import FinancingPlan
from .provenance import Input
from .purchase_accounting import StepUpCharges
from .synergies import SynergyYear


@dataclass(frozen=True)
class StandaloneYear:
    """One forward year of a company on its own, as the model needs it.

    Deliberately thin. A full 3-statement forward is Trellis's job; what the pro-forma
    combination needs is the income statement spine plus enough to compute tax.
    """
    year_index: int
    revenue: float
    operating_income: float
    net_income: float
    depreciation_amortisation: float = 0.0
    existing_intangible_amortisation: float = 0.0  # pre-deal, stays in adjusted
    interest_expense: float = 0.0  # the target's OWN interest, pre-deal


@dataclass(frozen=True)
class BridgeStep:
    label: str
    amount: float          # after-tax, signed, USD millions
    in_adjusted: bool      # does this step also hit adjusted earnings?
    note: str = ""


@dataclass(frozen=True)
class ProFormaYear:
    year_index: int
    ownership_fraction: float
    buyer_net_income: float
    steps: tuple[BridgeStep, ...]
    gaap_net_income: float
    adjusted_net_income: float
    gaap_shares: float
    adjusted_shares: float

    @property
    def gaap_eps(self) -> float:
        return self.gaap_net_income / self.gaap_shares

    @property
    def adjusted_eps(self) -> float:
        return self.adjusted_net_income / self.adjusted_shares

    def format(self) -> str:
        lines = [f"PRO-FORMA NET INCOME BRIDGE -- year {self.year_index}"
                 + (f" (target owned {self.ownership_fraction:.0%} of the year)"
                    if self.ownership_fraction < 1 else ""),
                 "-" * 78,
                 f"  {'Buyer standalone net income':<52} ${self.buyer_net_income:>12,.0f}mm"]
        for s in self.steps:
            marker = " " if s.in_adjusted else "*"
            lines.append(f"  {marker} {s.label:<50} ${s.amount:>12,.0f}mm")
        lines.append(f"  {'= Pro-forma net income (GAAP)':<52} ${self.gaap_net_income:>12,.0f}mm")
        lines.append(f"  {'= Pro-forma net income (adjusted)':<52} ${self.adjusted_net_income:>12,.0f}mm")
        lines.append("  * = excluded from adjusted earnings")
        for s in self.steps:
            if s.note:
                lines.append(f"    - {s.label}: {s.note}")
        return "\n".join(lines)


def combine(buyer: StandaloneYear, target: StandaloneYear,
            synergy: SynergyYear, charges: StepUpCharges,
            plan: FinancingPlan, buyer_tax_rate: Input, target_tax_rate: Input,
            buyer_shares: Input, ownership_fraction: float = 1.0,
            new_shares_issued: float = 0.0,
            expensed_transaction_costs_this_year: float = 0.0,
            eliminate_target_interest: bool = False) -> ProFormaYear:
    """Build one pro-forma year.

    `ownership_fraction` scales the target's contribution and the synergy realisation
    for a partial year -- the stub in the year of close. It does NOT scale financing
    cost by default, because debt raised at close accrues from close; callers wanting a
    stub-year financing charge should pass a plan sized to the stub. Making that
    explicit is better than a convenience that silently halves interest.

    `eliminate_target_interest` adds back the target's own pre-deal interest expense,
    after tax at the TARGET's rate. This is the adjustment that goes with repaying target
    debt in sources & uses: if the buyer funds the repayment, the target stops paying that
    interest, and leaving it in double-counts the cost of the same debt -- once in the
    target's contributed net income and again in the buyer's new acquisition interest.
    It is the only place the target's own tax rate legitimately enters the combination;
    everything else is taxed at the buyer's rate post-close.

    `expensed_transaction_costs_this_year` is advisory/legal cost expensed at close
    (ASC 805-10-25-23). It hits GAAP earnings in the year of close only, never adjusted,
    and never goodwill.
    """
    bt = buyer_tax_rate.required()
    tt = target_tax_rate.required()

    steps: list[BridgeStep] = []

    target_contribution = target.net_income * ownership_fraction
    steps.append(BridgeStep(
        "Target net income contributed", target_contribution, in_adjusted=True,
        note=(f"{ownership_fraction:.0%} of a full year"
              if ownership_fraction < 1 else "")))

    if eliminate_target_interest and target.interest_expense:
        steps.append(BridgeStep(
            "Target interest eliminated on refinancing (after tax)",
            target.interest_expense * (1 - tt) * ownership_fraction, in_adjusted=True,
            note=("taxed at the target's own rate -- this is pre-deal interest the "
                  "target no longer pays, not a buyer-level saving")))

    syn_after_tax = synergy.gross_pretax * (1 - bt) * ownership_fraction
    if syn_after_tax:
        steps.append(BridgeStep(
            "Synergies realised (after tax)", syn_after_tax, in_adjusted=True,
            note=f"pre-tax ${synergy.gross_pretax:,.0f}mm at this year's phase-in"))

    if synergy.cost_to_achieve:
        steps.append(BridgeStep(
            "Cost to achieve (after tax)",
            -synergy.cost_to_achieve * (1 - bt), in_adjusted=False,
            note="one-time integration/restructuring; excluded from adjusted by convention"))

    interest = plan.interest_expense(year_index=buyer.year_index)
    if interest:
        steps.append(BridgeStep(
            "Interest on acquisition debt (after tax)", -interest * (1 - bt),
            in_adjusted=True,
            note="stays in adjusted -- buyers exclude amortisation, not funding cost"))

    foregone = plan.foregone_interest_income()
    if foregone:
        steps.append(BridgeStep(
            "Foregone interest income on cash used (after tax)", -foregone * (1 - bt),
            in_adjusted=True,
            note="the charge most merger models omit entirely"))

    if charges.intangible_amortisation:
        steps.append(BridgeStep(
            "Intangible amortisation from step-up (after tax)",
            -charges.intangible_amortisation * (1 - bt), in_adjusted=False,
            note="non-cash; the single largest GAAP-vs-adjusted difference in most deals"))

    if charges.inventory_step_up_unwind:
        steps.append(BridgeStep(
            "Inventory step-up unwind (after tax)",
            -charges.inventory_step_up_unwind * (1 - bt), in_adjusted=False,
            note="non-recurring; unwinds through COGS within roughly one inventory turn"))

    if charges.incremental_depreciation:
        steps.append(BridgeStep(
            "Incremental depreciation on PP&E step-up (after tax)",
            -charges.incremental_depreciation * (1 - bt), in_adjusted=False))

    if expensed_transaction_costs_this_year:
        steps.append(BridgeStep(
            "Transaction costs expensed (after tax)",
            -expensed_transaction_costs_this_year * (1 - bt), in_adjusted=False,
            note="ASC 805: expensed as incurred, never capitalised into goodwill"))

    gaap = buyer.net_income + sum(s.amount for s in steps)
    adjusted = buyer.net_income + sum(s.amount for s in steps if s.in_adjusted)

    shares = buyer_shares.required() + new_shares_issued

    return ProFormaYear(
        year_index=buyer.year_index, ownership_fraction=ownership_fraction,
        buyer_net_income=buyer.net_income, steps=tuple(steps),
        gaap_net_income=gaap, adjusted_net_income=adjusted,
        gaap_shares=shares, adjusted_shares=shares,
    )
