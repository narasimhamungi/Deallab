"""Run the full J&J/Abiomed transaction model, across every financing scenario.

This is the payoff script: sourced deal terms + sourced target fundamentals + J&J's own
sourced purchase price allocation + a Trellis-derived buyer forecast, through the whole
engine, checked against J&J's own disclosed EPS guidance.

It runs the model once PER FINANCING SCENARIO rather than once. J&J never disclosed how
it funded the purchase (see deallab.deals.jnj_abiomed.FINANCING_MIX_NOT_DISCLOSED), and
its guidance was explicitly stated 'considering the impact of financing' -- so picking
one split would quietly determine the number the model is graded on. Spanning the range
converts an undisclosed input from a hidden assumption into a measured spread.

    python scripts/run_trellis_jnj.py      # first: produces the buyer forecast
    python scripts/run_jnj_abiomed.py      # then: this

Needs no network access -- everything is either in the deal file or in the forecast JSON.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from deallab import engine, guidance
from deallab import returns as returns_mod
from deallab import verdict as verdict_mod
from deallab.calendarize import FiscalCalendar, calendarize
from deallab.deals import jnj_abiomed as deal
from deallab.financing import DebtTranche, FinancingPlan
from deallab.loader import ForecastLoadError, load_standalone_years
from deallab.proforma import StandaloneYear
from deallab.provenance import assumed, sourced
from deallab.purchase_accounting import IntangibleClass
from deallab.synergies import (
    CostToAchieve,
    SynergyCase,
    SynergyItem,
    SynergyType,
)

FORECAST = ROOT / "data" / "jnj_standalone_forecast.json"
HORIZON = 5

# --- Inputs that are this SCRIPT's choices, not the deal file's ----------------------
# Kept here rather than in the deal file because they are modelling parameters, not
# facts about the transaction. The deal file holds what J&J and Abiomed disclosed; a
# discount rate and a synergy phase-in are the analyst's, and mixing the two would blur
# the line the whole provenance system exists to hold.

WACC = assumed("jnj_wacc", 0.075,
               "J&J is an AAA/AA-rated, low-beta large-cap pharma; 7.5% is a "
               "conventional mid-single-digit WACC for such an issuer in this period. "
               "Not derived from a CAPM build-up here -- ValuationLab does that "
               "properly and should supersede this if wired in.")
COST_OF_DEBT = assumed("acquisition_debt_rate", 0.045,
                       "Approximate investment-grade corporate yield available to a "
                       "top-rated issuer in late 2022, after the year's rate rises. "
                       "Not a sourced J&J issuance rate -- no issuance tied to this "
                       "deal was located (see FINANCING_MIX_NOT_DISCLOSED).")
FOREGONE_YIELD = assumed("foregone_yield_on_cash", 0.035,
                         "Short-dated yield J&J's marketable securities would have "
                         "earned in late 2022 / 2023. Below the debt rate, as it should "
                         "be for a short, high-quality portfolio.")


def _synergies() -> SynergyCase:
    """A deliberately THIN synergy case, and that is the finding, not a shortcut.

    J&J disclosed that Abiomed would run as a STANDALONE business within JJMT. That is
    an explicit decision to forgo the integration cost synergies a merger model normally
    assumes. Loading a generic percentage-of-opex cost synergy here would contradict a
    disclosed fact -- so the case carries revenue synergy only (J&J's own stated
    rationale: global scale and commercial reach applied to Impella), margined, phased
    slowly, with real cost to achieve.
    """
    return SynergyCase(
        items=(
            SynergyItem(
                "Commercial reach on Impella (J&J global scale)", SynergyType.REVENUE,
                assumed("revenue_synergy_run_rate_mm", 250.0,
                        "~24% uplift on Abiomed's ~$1.03bn revenue base at full "
                        "realisation. J&J's stated rationale was 'J&J's global scale "
                        "and commercial and clinical strength' applied to Impella -- "
                        "real, but unquantified by J&J. This is the analyst's number."),
                phase_in=(0.0, 0.15, 0.40, 0.70, 1.0),
                margin=assumed("revenue_synergy_margin", 0.45,
                               "Incremental contribution margin on device revenue "
                               "through an existing sales channel -- below Abiomed's "
                               "~80% gross margin, above a fully-loaded net margin."),
                source="J&J close 8-K rationale, quantification is the analyst's"),
        ),
        cost_to_achieve=CostToAchieve(
            (150.0, 100.0, 50.0),
            "Integration/commercial-enablement spend. Deliberately non-zero despite the "
            "standalone operating model: standing up cross-selling still costs money "
            "even when the acquired entity is not absorbed."),
    )


def _plan(cash_fraction: float, total_funding: float) -> FinancingPlan:
    cash = total_funding * cash_fraction
    debt = total_funding - cash
    return FinancingPlan(
        cash_on_hand_used=sourced("cash_used_mm", cash,
                                  "Scenario input -- see FINANCING_MIX_NOT_DISCLOSED"),
        foregone_yield=FOREGONE_YIELD,
        tranches=(
            (DebtTranche("Acquisition notes",
                         sourced("debt_mm", debt, "Scenario input"),
                         COST_OF_DEBT),)
            if debt > 0 else ()
        ),
        advisory_fees=deal.ADVISORY_FEES_PRETAX,
    )


def _target_years() -> tuple[StandaloneYear, ...]:
    """Abiomed forward years: normalised, projected, then calendarized onto J&J's year.

    NOT a Trellis run: Abiomed was acquired and stopped filing, so there is no forward
    XBRL to ingest. Three corrections applied, each of which an earlier version of this
    script got wrong:

    1. NORMALISED BASE. Abiomed's reported FY2022 operating income ($140.7mm) is
       depressed by a one-time $116mm acquired-IPR&D charge. Growing the reported figure
       projects a non-recurring charge forward forever. Uses
       TARGET_NORMALISED_OPERATING_INCOME_FY2022 ($256.7mm) instead, and scales net
       income by the same ratio -- an approximation, since the charge's tax effect is
       not separately disclosed, and flagged rather than presented as exact.

    2. CALENDARIZED. Abiomed's fiscal year ended 31 March; J&J's ends ~31 December.
       Abiomed FY2022 = April 2021 - March 2022, only three months of which fall inside
       J&J's calendar 2022. deallab.calendarize handles the nine-month offset.

    3. YEARS ALIGNED TO THE DEAL. Year 1 is FY2023 -- the first full year after the
       22 December 2022 close -- which is what J&J's own guidance addresses. The buyer
       forecast is built from the same FY2022 base for the same reason.
    """
    norm_op = deal.TARGET_NORMALISED_OPERATING_INCOME_FY2022.value
    reported_op = deal.TARGET_OPERATING_INCOME_FY2022.value
    normalisation = norm_op / reported_op

    rev = deal.TARGET_REVENUE_FY2022.value
    op = norm_op
    ni = deal.TARGET_NET_INCOME_FY2022.value * normalisation

    growth = [0.20, 0.18, 0.15, 0.13, 0.11]
    # Project on Abiomed's OWN fiscal calendar first (FY2023..FY2028), then calendarize.
    # An extra trailing year is generated because calendarizing year n needs n and n+1.
    fiscal: dict[int, dict[str, float]] = {}
    fy = 2022
    fiscal[fy] = {"revenue": rev, "operating_income": op, "net_income": ni}
    for g in growth + [0.10]:
        fy += 1
        rev *= (1 + g); op *= (1 + g); ni *= (1 + g)
        fiscal[fy] = {"revenue": rev, "operating_income": op, "net_income": ni}

    target_cal = FiscalCalendar("Abiomed", deal.TARGET_FISCAL_YEAR_END_MONTH)
    buyer_cal = FiscalCalendar("Johnson & Johnson", deal.BUYER_FISCAL_YEAR_END_MONTH)

    out = []
    for i in range(1, HORIZON + 1):
        cal = calendarize(fiscal, target_cal, buyer_cal,
                          buyer_fiscal_year=2022 + i,
                          items=("revenue", "operating_income", "net_income"))
        out.append(StandaloneYear(year_index=i, revenue=cal.values["revenue"],
                                  operating_income=cal.values["operating_income"],
                                  net_income=cal.values["net_income"]))
    return tuple(out)


def main() -> int:
    print("=" * 78)
    print("J&J / ABIOMED -- FULL TRANSACTION MODEL")
    print("=" * 78)

    if deal.MISSING:
        print(f"\n{len(deal.MISSING)} input(s) still uncollected -- the model runs, but "
              f"read these before trusting the output:")
        for i in deal.MISSING:
            print(f"  [{i.name}] {i.citation[:160]}...")

    try:
        buyer_years = load_standalone_years(FORECAST, expect_years=HORIZON)
    except ForecastLoadError as e:
        print(f"\nCANNOT RUN: {e}")
        return 1

    print(f"\nBuyer forecast loaded: {len(buyer_years)} years, "
          f"FY{buyer_years[0].revenue:,.0f}mm revenue in year 1")
    target_years = _target_years()
    synergies = _synergies()

    intangibles = (
        IntangibleClass("Amortizable intangibles (Impella in-market products)",
                        deal.INTANGIBLE_AMORTIZABLE_FV,
                        sourced("intangible_life_years", 14.0,
                                "'average weighted life of 14 years' -- " + deal.JNJ_10Q_Q1_2023)),
        # IPR&D: indefinite-lived under ASC 350-30, so identifiable (reduces goodwill)
        # but never amortised. Excluding it entirely -- as an earlier version did --
        # overstated goodwill by its full $1.1bn.
        IntangibleClass("IPR&D (unapproved Impella programs)", deal.IPRD_FV,
                        useful_life_years=None),
    )

    # Funding needed = what leaves (consideration + expensed fees) LESS what comes with
    # the target. Abiomed had ~$1bn of net cash and no debt, so that cash arrives at
    # close and funds part of the price -- sources & uses treats it as a source, and
    # sizing the funding plan without netting it raises $1bn too much. The engine's own
    # balance check caught exactly this on the first run of this script; the fix belongs
    # here, in the caller that sizes the plan, not in sources_uses.py.
    # Funding needed = UPFRONT consideration only. The CVR is deliberately excluded:
    # sources_uses.build() (fund_contingent_at_close=False, the default) correctly
    # treats it as an ASC 805 liability, not day-one cash -- so sizing the funding plan
    # off total_equity_purchase_price() (which INCLUDES the CVR) raised $781mm more
    # than the deal actually needed at close, and sources & uses failed its own balance
    # check by exactly that amount on the first real-data run. Fixed here, at the one
    # place that decides how much to raise, matching the treatment already correct in
    # sources_uses.py.
    total_funding = (deal.TERMS.upfront_equity_purchase_price()
                     + deal.ADVISORY_FEES_PRETAX.value
                     + deal.TARGET_NET_DEBT.value)  # negative = net cash, reduces need

    results = []
    for label, cash_fraction, rationale in deal.FINANCING_SCENARIOS:
        plan = _plan(cash_fraction, total_funding)
        model = engine.DealModel(
            terms=deal.TERMS, plan=plan, synergies=synergies, intangibles=intangibles,
            buyer_years=buyer_years, target_years=target_years,
            buyer_shares=deal.BUYER_DILUTED_SHARES,
            buyer_tax_rate=deal.BUYER_TAX_RATE_OVERRIDE,
            target_tax_rate=deal.TARGET_EFFECTIVE_TAX_RATE_FY2022,
            target_book_equity=deal.TARGET_BOOK_EQUITY,
            sourced_deferred_tax_liability=deal.DEFERRED_TAX_LIABILITY_ABIOMED,
            stub_fraction_year_one=1.0,  # year 1 = first FULL year post-close (2023)
            refinance_target_debt=True,
        )
        result = engine.run(model)
        results.append((label, cash_fraction, rationale, result))

    # --- Per-scenario detail, then the spread ---------------------------------------
    base_label, _, _, base = results[0]
    print("\n" + "=" * 78)
    print(f"DETAIL -- scenario: {base_label}")
    print("=" * 78)
    print(base.format())

    print("\n" + "=" * 78)
    print("FINANCING SENSITIVITY -- the undisclosed input, spanned rather than guessed")
    print("=" * 78)
    print(f"  {'Scenario':<28}{'Yr1 adj':>10}{'Yr1 GAAP':>11}{'Yr2 adj':>10}"
          f"{'Breakeven syn':>16}")
    for label, _, _, r in results:
        print(f"  {label:<28}{r.accretion[0].adjusted_pct:>9.2%}"
              f"{r.accretion[0].gaap_pct:>11.2%}{r.accretion[1].adjusted_pct:>10.2%}"
              f"{r.breakeven.required_pretax:>15,.0f}mm")

    y1_adj = [r.accretion[0].adjusted_pct for _, _, _, r in results]
    spread = max(y1_adj) - min(y1_adj)
    print(f"\n  Year-1 adjusted accretion spread across the funding range: {spread:.2%}")
    verdicts = {r.accretion[0].adjusted_verdict for _, _, _, r in results}
    if len(verdicts) == 1:
        print(f"  Every scenario lands on the same verdict ({verdicts.pop()}) -- the "
              f"undisclosed funding mix does NOT change the conclusion. That is the "
              f"strongest form this finding can take given the disclosure gap.")
    else:
        print(f"  The verdict CHANGES across the funding range ({sorted(verdicts)}). "
              f"The undisclosed mix is therefore load-bearing, and no single answer to "
              f"'is this accretive' is defensible without knowing it. Report the range.")

    print("\n" + "=" * 78)
    print("PPA CROSS-CHECK -- model's DERIVED goodwill vs. J&J's own DISCLOSED figure")
    print("=" * 78)
    derived_gw = base.allocation.goodwill
    actual_gw = deal.ACTUAL_PPA["goodwill_mm"]
    gw_gap = derived_gw - actual_gw
    print(f"  Model-derived goodwill   ${derived_gw:>12,.0f}mm")
    print(f"  J&J's disclosed goodwill ${actual_gw:>12,.0f}mm")
    print(f"  Gap                      ${gw_gap:>12,.0f}mm  ({gw_gap / actual_gw:+.1%})")
    print("  This is a genuine independent check: goodwill here is a RESIDUAL the model")
    print("  computes from consideration, book equity, the intangible step-up and the")
    print("  DTL -- none of it read from J&J's own goodwill line. Landing close means")
    print("  the consideration, share count, CVR weight and step-up all hang together.")
    print("  Known reconciling items, both of which the model does NOT carry and which")
    print("  push in OPPOSITE directions -- so the residual gap is a net, not a single")
    print("  missing piece:")
    print("   (a) ~$0.7bn of other identifiable assets (receivables, inventory, PP&E)")
    print("       that J&J allocated but this model has no sourced figures for. Adding")
    print("       them would push derived goodwill DOWN, widening the gap.")
    print("   (b) liabilities assumed, which this model estimates at ~$1,957mm but does")
    print("       not feed into the allocation. Adding them would push goodwill UP,")
    print("       narrowing it.")
    print("  Tracking this gap honestly is the point. An earlier version of this script")
    print("  landed 2.4% away with a WORSE model (IPR&D dumped into goodwill, DTL")
    print("  self-computed); tightening both inputs moved the answer further from J&J's")
    print("  number, not closer. Proximity to a disclosed figure is not evidence of")
    print("  correctness when the inputs behind it are known to be wrong.")
    for n in base.allocation.notes:
        print(f"  ! {n}")

    # --- Economic lens: returns, standalone value, the two verdicts -----------------
    # This section is why DealLab exists. An earlier version of this script stopped at
    # accretion/dilution -- which is precisely the failure the whole repo was built to
    # avoid, since accretion is an artefact of relative P/E and funding cost and says
    # nothing about whether the price was right.

    tax = deal.BUYER_TAX_RATE_OVERRIDE.value
    syn_npv = synergies.npv(WACC, deal.BUYER_TAX_RATE_OVERRIDE, years=10)
    syn_npv_ex_rev = synergies.npv_excluding_revenue_synergies(
        WACC, deal.BUYER_TAX_RATE_OVERRIDE, years=10)

    # Unlevered FCF to the acquired business: after-tax operating profit plus realised
    # synergies. Deliberately crude -- no working-capital or capex build for Abiomed,
    # because neither is sourced post-close. Stated rather than silently smoothed.
    fcf = [t.operating_income * (1 - tax) + synergies.year(i).net_pretax * (1 - tax)
           for i, t in enumerate(target_years, start=1)]
    # entry_ebitda uses YEAR 1 (closest available proxy to the actual deal-date run
    # rate) -- NOT year 5. An earlier version divided the deal EV by YEAR 5's EBITDA to
    # get "entry_multiple", then applied that SAME multiple at exit. That is circular:
    # exit_equity = exit_ebitda * exit_multiple = exit_ebitda * (EV / exit_ebitda) = EV,
    # algebraically, no matter how much the business actually grows between year 1 and
    # year 5. The "conservative convention" is supposed to mean "hold the multiple flat,
    # still credit the earnings growth" -- not erase the growth entirely by defining the
    # multiple in terms of the exit figure it is later applied to. Caught because MOIC
    # came back at 1.05x and IRR near 1% for a business modelled to grow double digits,
    # which does not happen without a real construction error.
    entry_ebitda = target_years[0].operating_income
    exit_ebitda = target_years[-1].operating_income  # EBITDA proxy: no D&A sourced
    entry_multiple = deal.TERMS.implied_enterprise_value() / entry_ebitda

    rets = returns_mod.run(
        entry_equity_outlay=sourced("entry_outlay_mm",
                                    deal.TERMS.total_equity_purchase_price(),
                                    "Total consideration incl. CVR at fair value"),
        free_cash_flows=fcf,
        exit_ebitda=sourced("exit_ebitda_mm", exit_ebitda,
                            "Year-5 projected operating income as an EBITDA proxy -- "
                            "no post-close D&A for Abiomed is sourced"),
        exit_multiple=assumed("exit_multiple", entry_multiple,
                              "Set equal to entry -- the conservative convention, "
                              "crediting no multiple re-rating"),
        exit_net_debt=sourced("exit_net_debt_mm", 0.0,
                              "Abiomed carried no debt and its cash was acquired"),
        hurdle_rate=WACC, entry_multiple=entry_multiple)

    print("\n" + "=" * 78)
    print(rets.format())

    # Standalone value: the market's own unaffected assessment, not a ValuationLab run.
    unaffected_equity = (deal.TARGET_SHARES_OUTSTANDING.value
                         * deal.TARGET_SHARE_PRICE_UNAFFECTED.value)
    unaffected_ev = unaffected_equity + deal.TARGET_NET_DEBT.value
    standalone_basis = (
        f"Unaffected market EV: {deal.TARGET_SHARES_OUTSTANDING.value:,.2f}mm shares x "
        f"${deal.TARGET_SHARE_PRICE_UNAFFECTED.value:.2f} (last close before "
        f"announcement) less ${-deal.TARGET_NET_DEBT.value:,.0f}mm net cash. This is "
        f"the MARKET's standalone view, not an intrinsic valuation. ValuationLab is the "
        f"better anchor and deallab.bridge.standalone_value is built to consume its "
        f"Conclusion -- but running it needs an Abiomed peer set and DCF inputs that "
        f"have not been collected, and inventing them to fill this slot would be worse "
        f"than using a real market price. NOTE the unaffected price itself is still "
        f"SECONDARY-sourced (see the deal file), so this anchor inherits that weakness.")

    econ = verdict_mod.build_economic_verdict(
        price_paid=deal.TERMS.total_equity_purchase_price(),
        standalone_value=unaffected_ev, standalone_basis=standalone_basis,
        synergy_npv=syn_npv.net_npv, synergy_npv_ex_revenue=syn_npv_ex_rev.net_npv,
        irr=rets.irr, wacc=WACC.value, extra_warnings=rets.warnings)
    acct = verdict_mod.build_accounting_verdict(list(base.accretion), base.breakeven)

    print("\n" + "=" * 78)
    print(verdict_mod.build(acct, econ).format())

    # --- Against J&J's own disclosed guidance ---------------------------------------
    print("\n" + "=" * 78)
    checks = []
    for label, _, _, r in results:
        checks.append(guidance.check_range(
            f"Year 1 adjusted EPS -- {label}", "adjusted",
            deal.GUIDANCE["year_one_adjusted_eps"],
            *deal.GUIDANCE_YEAR_ONE_BOUNDS,
            modelled=r.accretion[0].adjusted_pct))
    print(guidance.GuidanceReport(tuple(checks)).format())

    print("\n" + "=" * 78)
    print("NOTE ON WHAT THIS IS AND IS NOT")
    print("=" * 78)
    print("  Sourced: deal terms, CVR structure, target fundamentals, J&J's own PPA,")
    print("  the deferred tax liability, buyer share count, disclosed EPS guidance.")
    print("  Analyst's own: synergy case (J&J quantified none), discount and debt")
    print("  rates, Abiomed's forward growth (it stopped filing post-close), the CVR")
    print("  probability weight, and the forecast driver window. Every one of those is")
    print("  in the assumption register above -- the conclusion is only as good as they")
    print("  are, and the financing spread shows how much one of them actually moves it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
