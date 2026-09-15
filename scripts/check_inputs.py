"""Collection status for the J&J/Abiomed model.

Run this first. It reports exactly which inputs are sourced, which are derived, which
are assumed, and which have not been collected -- with the filing that contains each
missing one. The model will not run until the missing list is empty, and that refusal is
deliberate: a merger model that defaults its way past a gap produces an answer
indistinguishable from a researched one.

    python scripts/check_inputs.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from deallab.deals import jnj_abiomed as deal
from deallab.provenance import AssumptionRegister


def main() -> int:
    print(f"{deal.TERMS.acquirer} / {deal.TERMS.target}")
    print(f"Announced {deal.TERMS.announced}, closed {deal.TERMS.closed}\n")

    print("COLLECTED")
    print("-" * 72)
    for i in (deal.CASH_PER_SHARE, deal.CVR.max_per_share, deal.STATED_EV,
              deal.TARGET_SHARES_OUTSTANDING, deal.TARGET_SHARE_PRICE_UNAFFECTED,
              deal.TARGET_REVENUE_FY2022, deal.TARGET_OPERATING_INCOME_FY2022,
              deal.TARGET_NET_INCOME_FY2022, deal.TARGET_EFFECTIVE_TAX_RATE_FY2022,
              deal.TARGET_NET_DEBT, deal.TARGET_BOOK_EQUITY):
        flag = " [SECONDARY]" if "SECONDARY SOURCE" in i.citation else ""
        print(f"  {i.basis.value:<13} {i.name:<38} {i.value:>12,.4g}{flag}")

    print("\nDERIVED CHECKS")
    print("-" * 72)
    upfront = deal.TERMS.upfront_equity_purchase_price()
    implied_ev_ex_cvr = upfront + deal.TARGET_NET_DEBT.value
    gap_ex_cvr = implied_ev_ex_cvr - deal.STATED_EV.value
    print(f"  Upfront equity consideration        ${upfront:>12,.0f}mm")
    print(f"  Actual target net cash (sourced)    ${-deal.TARGET_NET_DEBT.value:>12,.0f}mm  "
          f"(30 Jun 2022 10-Q, no debt)")
    print(f"  Derived EV, upfront only, excl. CVR ${implied_ev_ex_cvr:>12,.0f}mm")
    print(f"  Stated EV (incl. cash acquired)     ${deal.STATED_EV.value:>12,.0f}mm")
    print(f"  GAP (upfront only)                  ${gap_ex_cvr:>12,.0f}mm  "
          f"({gap_ex_cvr / deal.STATED_EV.value:+.1%})")
    print("    -> real and unresolved, not a rounding artefact. See the module")
    print("       docstring for two candidate readings, neither confirmed.")
    ev_incl_cvr = deal.TERMS.implied_enterprise_value()
    gap_incl_cvr = ev_incl_cvr - deal.STATED_EV.value
    print(f"  Derived EV, incl. CVR at assumed FV ${ev_incl_cvr:>12,.0f}mm  "
          f"(CVR FV ${deal.TERMS.contingent_consideration_fair_value():,.0f}mm at "
          f"weight {deal.CVR.probability_weight.value:.3f})")
    print(f"  GAP (incl. CVR)                     ${gap_incl_cvr:>12,.0f}mm  "
          f"({gap_incl_cvr / deal.STATED_EV.value:+.1%})")
    print("    -> tighter than the upfront-only gap, and on the OPPOSITE side, once")
    print("       the CVR is included at its (circumstantial, not confirmed) fair")
    print("       value. Suggestive that the stated EV isn't upfront-cash-only --")
    print("       not proof, since the CVR weight behind it is itself an estimate.")
    print("       Do not plug a number here to force a match -- state both gaps.")
    premium = deal.TERMS.premium_to_unaffected()
    print(f"  Upfront premium to unaffected price {premium:>12.1%}")
    print(f"  CVR maximum as % of upfront price   "
          f"{deal.CVR.max_per_share.value / deal.CASH_PER_SHARE.value:>12.1%}")

    reg = AssumptionRegister()
    reg.record(deal.CVR.probability_weight, *deal.MISSING)

    print("\n" + reg.report())

    print("\nJ&J's OWN PURCHASE PRICE ALLOCATION (sourced this pass -- cross-check, not")
    print("model input for goodwill/intangibles, which the model derives independently)")
    print("-" * 72)
    for k, v in deal.ACTUAL_PPA.items():
        label = "CVR max (undiscounted)" if "cvr" in k else k.replace("_mm", "").replace("_", " ")
        print(f"  {label:<38} ${v:>12,.1f}mm")
    print(f"  {deal.ACTUAL_PPA_SOURCE}")
    print(f"\n  {deal.PPA_MEASUREMENT_PERIOD_ADJUSTMENT}")
    print(f"\n  {deal.EV_RESTATEMENT_NOTE}")

    print("\nANSWER KEY (what the model will be checked against)")
    print("-" * 72)
    for k, v in deal.GUIDANCE.items():
        print(f"  [{k}]\n    {v}\n")

    missing = len(reg.missing)
    print(f"STATUS: {missing} input group(s) outstanding. "
          f"{'Model cannot run.' if missing else 'Ready to run.'}")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
