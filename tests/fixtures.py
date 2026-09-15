"""
A synthetic transaction used to verify arithmetic.

Every number here is INVENTED. This fixture exists to check that the mechanics are
right -- that sources equal uses, that goodwill is the residual, that the DTL increases
goodwill, that amortisation stops at the end of its useful life. It is not a deal and
no conclusion about any real transaction should be drawn from it.

It is deliberately NOT the J&J/Abiomed fixture. Testing the mechanics against invented
round numbers and then running the real deal separately keeps the two apart: a test
suite built on the real deal's numbers would pass or fail for reasons that have nothing
to do with whether the code is correct, and would make it tempting to adjust the real
inputs until the tests went green.

Round numbers are chosen so expected values can be computed by hand in the test and
compared, rather than snapshotted from the code's own output -- a snapshot test of an
arithmetic module verifies only that the code has not changed, not that it is right.
"""

from __future__ import annotations

from deallab.financing import DebtTranche, FinancingPlan
from deallab.proforma import StandaloneYear
from deallab.provenance import assumed, sourced
from deallab.purchase_accounting import IntangibleClass
from deallab.synergies import CostToAchieve, SynergyCase, SynergyItem, SynergyType
from deallab.terms import Consideration, ContingentValueRight, DealTerms

CITE = "SYNTHETIC -- invented for arithmetic verification, not a real figure"


def terms(with_cvr: bool = True) -> DealTerms:
    cvr = ContingentValueRight(
        max_per_share=sourced("cvr_max", 10.00, CITE),
        probability_weight=assumed("cvr_weight", 0.40, CITE),
        milestones="synthetic single milestone",
    ) if with_cvr else None
    return DealTerms(
        acquirer="BuyerCo", target="TargetCo",
        announced="2024-01-01", closed="2024-06-30",
        consideration_type=Consideration.ALL_CASH,
        cash_per_share=sourced("cash_per_share", 100.00, CITE),
        target_shares_outstanding=sourced("shares_mm", 50.0, CITE),
        target_net_debt=sourced("net_debt_mm", 500.0, CITE),
        stated_enterprise_value=sourced("stated_ev_mm", 5_700.0, CITE),
        cvr=cvr,
        target_share_price_unaffected=sourced("unaffected", 80.00, CITE),
        source=CITE,
    )


def plan(cash: float = 1_000.0, debt: float = 4_000.0,
         equity_mm: float | None = None) -> FinancingPlan:
    return FinancingPlan(
        cash_on_hand_used=sourced("cash_used_mm", cash, CITE),
        foregone_yield=assumed("foregone_yield", 0.04, CITE),
        tranches=(
            DebtTranche(
                label="Term loan",
                principal=sourced("term_loan_mm", debt, CITE),
                rate=sourced("term_loan_rate", 0.05, CITE),
            ),
        ) if debt else (),
        new_equity_issued=sourced("equity_mm", equity_mm, CITE) if equity_mm else None,
        new_equity_price=sourced("equity_price", 50.0, CITE) if equity_mm else None,
        advisory_fees=sourced("advisory_mm", 50.0, CITE),
    )


def intangibles() -> tuple[IntangibleClass, ...]:
    return (
        IntangibleClass("Developed technology",
                        sourced("dev_tech_mm", 2_000.0, CITE),
                        sourced("dev_tech_life", 10.0, CITE)),
        IntangibleClass("Customer relationships",
                        sourced("cust_rel_mm", 1_000.0, CITE),
                        sourced("cust_rel_life", 5.0, CITE)),
    )


def synergy_case() -> SynergyCase:
    return SynergyCase(
        items=(
            SynergyItem("Procurement and overhead", SynergyType.COST,
                        sourced("cost_syn_mm", 200.0, CITE),
                        phase_in=(0.25, 0.50, 0.75, 1.0, 1.0)),
            SynergyItem("Cross-sell", SynergyType.REVENUE,
                        sourced("rev_syn_mm", 300.0, CITE),
                        phase_in=(0.0, 0.20, 0.50, 0.80, 1.0),
                        margin=assumed("rev_syn_margin", 0.40, CITE)),
        ),
        cost_to_achieve=CostToAchieve((150.0, 100.0, 50.0), CITE),
    )


def buyer_years(n: int = 5, net_income: float = 5_000.0) -> tuple[StandaloneYear, ...]:
    return tuple(
        StandaloneYear(year_index=i, revenue=40_000.0 * (1.03 ** (i - 1)),
                       operating_income=8_000.0 * (1.03 ** (i - 1)),
                       net_income=net_income * (1.03 ** (i - 1)))
        for i in range(1, n + 1)
    )


def target_years(n: int = 5) -> tuple[StandaloneYear, ...]:
    return tuple(
        StandaloneYear(year_index=i, revenue=1_000.0 * (1.15 ** (i - 1)),
                       operating_income=200.0 * (1.15 ** (i - 1)),
                       net_income=150.0 * (1.15 ** (i - 1)))
        for i in range(1, n + 1)
    )
