"""
End-to-end orchestration: terms in, verdict out, with every stage's output preserved.

The engine deliberately keeps each stage's result rather than threading a single mutable
state object through. A merger model's usefulness is in the intermediate tables -- the
sources & uses, the allocation, the bridge -- and a pipeline that only surfaces the final
number throws away everything a reviewer needs to challenge it.

Ordering is fixed and matters: terms determine consideration, consideration drives the
allocation, the allocation drives the step-up charges, the charges and the financing cost
drive the pro-forma bridge, the bridge drives accretion, and only then do the two verdicts
get built. The assumption register is passed through every stage and reported first,
before any result, because the assumptions are the thing the conclusion rests on.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import accretion, proforma, purchase_accounting, sources_uses, verdict
from .financing import FinancingPlan
from .provenance import AssumptionRegister, Input
from .purchase_accounting import AllocationResult, IntangibleClass
from .returns import ReturnsResult
from .synergies import SynergyCase
from .terms import DealTerms


@dataclass
class DealModel:
    """Everything needed to run one transaction, in one place."""
    terms: DealTerms
    plan: FinancingPlan
    synergies: SynergyCase
    intangibles: tuple[IntangibleClass, ...]
    buyer_years: tuple[proforma.StandaloneYear, ...]
    target_years: tuple[proforma.StandaloneYear, ...]
    buyer_shares: Input
    buyer_tax_rate: Input
    target_tax_rate: Input
    target_book_equity: Input
    inventory_step_up: Input | None = None
    ppe_step_up: Input | None = None
    sourced_deferred_tax_liability: Input | None = None
    ppe_remaining_life_years: Input | None = None
    stub_fraction_year_one: float = 1.0
    refinance_target_debt: bool = True
    register: AssumptionRegister = field(default_factory=AssumptionRegister)

    def __post_init__(self):
        if len(self.buyer_years) != len(self.target_years):
            raise ValueError(
                f"buyer_years has {len(self.buyer_years)} entries, target_years has "
                f"{len(self.target_years)}. The pro-forma combination needs both sides "
                f"for every modelled year; a mismatch means one forecast is short and "
                f"the missing years would be silently dropped.")
        self.terms.register(self.register)
        self.plan.register(self.register)
        self.synergies.register(self.register)
        purchase_accounting.register(
            self.register, self.intangibles, self.buyer_tax_rate,
            self.target_tax_rate, self.target_book_equity, self.buyer_shares,
            self.inventory_step_up, self.ppe_step_up, self.ppe_remaining_life_years,
            self.sourced_deferred_tax_liability)


@dataclass(frozen=True)
class DealResult:
    sources_uses: sources_uses.SourcesUses
    allocation: AllocationResult
    pro_forma: tuple[proforma.ProFormaYear, ...]
    accretion: tuple[accretion.AccretionResult, ...]
    breakeven: accretion.BreakevenSynergies
    register: AssumptionRegister
    ev_reconciliation: str
    premium_to_unaffected: float | None

    def format(self) -> str:
        parts = [self.register.report(), "",
                 self.sources_uses.format(), "",
                 f"  {self.ev_reconciliation}"]
        if self.premium_to_unaffected is not None:
            parts.append(f"  Upfront premium to unaffected price: "
                         f"{self.premium_to_unaffected:+.1%} (excludes CVR -- a premium "
                         f"quoted inclusive of a contingent payout is a maximum, not a "
                         f"premium)")
        parts += ["", self.allocation.format(), ""]
        for pf in self.pro_forma:
            parts += [pf.format(), ""]
        for a in self.accretion:
            parts += [a.format(), ""]
        return "\n".join(parts)


def run(model: DealModel) -> DealResult:
    """Execute the full transaction model."""
    su = sources_uses.build(model.terms, model.plan,
                            refinance_target_debt=model.refinance_target_debt)

    consideration = model.terms.total_equity_purchase_price()
    allocation = purchase_accounting.allocate(
        consideration_transferred=consideration,
        target_book_equity=model.target_book_equity,
        intangibles=model.intangibles,
        buyer_tax_rate=model.buyer_tax_rate,
        inventory_step_up=model.inventory_step_up,
        ppe_step_up=model.ppe_step_up,
        sourced_deferred_tax_liability=model.sourced_deferred_tax_liability,
    )

    new_shares = model.plan.new_shares_issued()
    pro_formas: list[proforma.ProFormaYear] = []
    accretions: list[accretion.AccretionResult] = []

    for i, (b, t) in enumerate(zip(model.buyer_years, model.target_years), start=1):
        ownership = model.stub_fraction_year_one if i == 1 else 1.0
        charges = purchase_accounting.step_up_charges(
            i, model.intangibles, allocation,
            ppe_remaining_life_years=model.ppe_remaining_life_years)
        pf = proforma.combine(
            buyer=b, target=t, synergy=model.synergies.year(i), charges=charges,
            plan=model.plan, buyer_tax_rate=model.buyer_tax_rate,
            target_tax_rate=model.target_tax_rate, buyer_shares=model.buyer_shares,
            ownership_fraction=ownership, new_shares_issued=new_shares,
            expensed_transaction_costs_this_year=(
                model.plan.expensed_transaction_costs() if i == 1 else 0.0),
            eliminate_target_interest=model.refinance_target_debt,
        )
        pro_formas.append(pf)
        accretions.append(accretion.compute(pf, b.net_income, model.buyer_shares.required()))

    first = pro_formas[0]
    breakeven = accretion.breakeven_synergies(
        first, model.buyer_years[0].net_income, model.buyer_shares.required(),
        model.buyer_tax_rate.required(),
        realised_pretax_synergies=model.synergies.year(1).gross_pretax
        * model.stub_fraction_year_one,
        target_revenue=model.target_years[0].revenue,
    )

    return DealResult(
        sources_uses=su, allocation=allocation, pro_forma=tuple(pro_formas),
        accretion=tuple(accretions), breakeven=breakeven, register=model.register,
        ev_reconciliation=model.terms.ev_reconciliation(),
        premium_to_unaffected=model.terms.premium_to_unaffected(),
    )


def build_verdict(result: DealResult, standalone_value: float | None,
                  standalone_basis: str, synergy_npv: float | None,
                  synergy_npv_ex_revenue: float | None = None,
                  returns: ReturnsResult | None = None,
                  wacc: float | None = None,
                  price_paid: float | None = None) -> verdict.DealVerdict:
    """Assemble the two-lens verdict from a completed run."""
    acc = verdict.build_accounting_verdict(list(result.accretion), result.breakeven)
    econ = verdict.build_economic_verdict(
        price_paid=price_paid if price_paid is not None
        else result.allocation.consideration_transferred,
        standalone_value=standalone_value, standalone_basis=standalone_basis,
        synergy_npv=synergy_npv, synergy_npv_ex_revenue=synergy_npv_ex_revenue,
        irr=returns.irr if returns else None, wacc=wacc,
        extra_warnings=returns.warnings if returns else (),
    )
    return verdict.build(acc, econ)
