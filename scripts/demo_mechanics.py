"""End-to-end run on the SYNTHETIC fixture, to exercise the mechanics.

Every number in this run is invented. It exists to show the shape of the output and to
prove the pipeline runs end to end without the real deal's inputs collected. No
conclusion about any real transaction should be drawn from it.

    python scripts/demo_mechanics.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from fixtures import (
    CITE,
    buyer_years,
    intangibles,
    plan,
    synergy_case,
    target_years,
    terms,
)

from deallab import engine
from deallab.provenance import assumed, sourced
from deallab.returns import run as run_returns


def main() -> int:
    print("=" * 76)
    print("SYNTHETIC DEMONSTRATION -- every figure below is invented")
    print("=" * 76 + "\n")

    model = engine.DealModel(
        terms=terms(), plan=plan(cash=1_750.0, debt=4_000.0),
        synergies=synergy_case(), intangibles=intangibles(),
        buyer_years=buyer_years(), target_years=target_years(),
        buyer_shares=sourced("shares_mm", 1_000.0, CITE),
        buyer_tax_rate=sourced("buyer_tax", 0.21, CITE),
        target_tax_rate=sourced("target_tax", 0.21, CITE),
        target_book_equity=sourced("book_mm", 1_000.0, CITE),
        inventory_step_up=sourced("inv_step_up", 120.0, CITE),
        stub_fraction_year_one=0.5,
    )
    result = engine.run(model)
    print(result.format())

    wacc, tax = sourced("wacc", 0.08, CITE), sourced("tax", 0.21, CITE)
    npv = model.synergies.npv(wacc, tax, years=10)
    ex_rev = model.synergies.npv_excluding_revenue_synergies(wacc, tax, years=10)
    print(npv.format())
    print(f"\n  Excluding revenue synergies: ${ex_rev.net_npv:,.0f}mm "
          f"({ex_rev.net_npv / npv.net_npv - 1:+.0%})\n")

    returns = run_returns(
        entry_equity_outlay=sourced("entry", model.terms.total_equity_purchase_price(), CITE),
        free_cash_flows=[120.0, 160.0, 210.0, 260.0, 320.0],
        exit_ebitda=sourced("exit_ebitda", 520.0, CITE),
        exit_multiple=assumed("exit_mult", 15.0, CITE),
        exit_net_debt=sourced("exit_nd", 0.0, CITE),
        hurdle_rate=wacc, entry_multiple=15.0,
    )
    print(returns.format() + "\n")

    verdict = engine.build_verdict(
        result, standalone_value=4_200.0,
        standalone_basis="SYNTHETIC -- stands in for a ValuationLab anchor",
        synergy_npv=npv.net_npv, synergy_npv_ex_revenue=ex_rev.net_npv,
        returns=returns, wacc=0.08)
    print(verdict.format())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
