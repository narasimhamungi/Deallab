"""Pull J&J's own standalone forecast through the real Trellis pipeline.

This is the buyer_standalone_forecast item from deallab.deals.jnj_abiomed.MISSING --
a pipeline run against live SEC EDGAR data, not a research task. J&J (CIK 200406) is
already in Trellis's validated registry, so this is: fetch -> build -> check -> forecast,
the same four steps ValuationLab runs for every company it touches.

Needs network access to data.sec.gov, which this sandbox's egress proxy does not allow
(it's locked to package registries -- PyPI, GitHub, npm -- not general web access). Run
this on your own machine, where Trellis is already installed per RUNNING.md.

    export TRELLIS_USER_AGENT="YourName your-email@example.com"   # SEC requires this
    python scripts/run_trellis_jnj.py

Writes the forecast to data/jnj_standalone_forecast.json in DealLab's own $mm units
(Trellis reports raw as-filed dollars; DealLab works in millions throughout -- the
conversion happens once, here, rather than being left for a script to get wrong later).
"""
import dataclasses
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from deallab.deals import jnj_abiomed as deal

JNJ_CIK = 200406


def main() -> int:
    try:
        from trellis.companies import get_profile
        from trellis.forecast import derive_drivers_from_history, run_forecast
        from trellis.ingest import IngestionError, fetch_all
        from trellis.statements import (
            build_annual_table,
            fill_derived_gaps,
            fiscal_year_key,
            run_all_checks,
        )
    except ImportError as e:
        print(f"Trellis is not installed: {e}")
        print("pip install git+https://github.com/narasimhamungi/trellis.git")
        return 1

    profile = get_profile(JNJ_CIK)
    print(f"{profile.name} ({profile.ticker}), CIK {profile.cik}")
    print(f"Fiscal year end: {profile.fiscal_year_end}")
    if profile.notes:
        print(f"Registry notes: {profile.notes[:200]}...")
    print()

    print("Fetching from SEC EDGAR company-facts XBRL (needs TRELLIS_USER_AGENT set)...")
    try:
        obs = fetch_all(cik=JNJ_CIK)
    except IngestionError as e:
        print(f"INGESTION FAILED: {e}")
        print("If this is the user-agent error: export TRELLIS_USER_AGENT first.")
        return 1
    print(f"Fetched {len(obs)} canonical line items.\n")

    built = build_annual_table(obs)
    years = sorted(built.table)
    print(f"Historical years built: {years}")
    if built.fye_collisions:
        print(f"FYE collisions ({len(built.fye_collisions)}) -- read before trusting "
              f"which period won:")
        for c in built.fye_collisions:
            print(f"  {c}")
    if built.stub_periods:
        print(f"Stub periods ({len(built.stub_periods)}):")
        for s in built.stub_periods:
            print(f"  {s}")

    derived = fill_derived_gaps(built.table)
    if derived:
        print(f"\nDerived (gap-filled) fields ({len(derived)}):")
        for d in derived:
            print(f"  FY{d.year} {d.canonical_name} via {d.method}")

    checks = run_all_checks(built.table)
    hard_fails = [c for c in checks if not c.passed and c.kind == "hard"]
    soft_fails = [c for c in checks if not c.passed and c.kind == "soft"]
    print(f"\nStructural checks: {len(checks)} run, {len(hard_fails)} hard failures, "
          f"{len(soft_fails)} soft warnings.")
    for c in hard_fails:
        print(f"  HARD FAIL  {c.name}: {c.detail}")
    for c in soft_fails:
        print(f"  soft warn  {c.name}: {c.detail}")
    # A hard failure that never stops anything is not a hard failure. This script
    # previously printed "treat anything downstream as suspect" and continued, every
    # run, on FY2006/FY2007 balance-sheet gaps two decades outside the window this
    # model actually uses -- which trains the reader to scroll past the loudest signal
    # the tool produces. So the failures are scoped: re-run the same checks over ONLY
    # the years the drivers are derived from, and block on those.
    window_start = deal.BUYER_FORECAST_BASE_YEAR - deal.BUYER_DRIVER_LOOKBACK_YEARS + 1
    window = {y: v for y, v in built.table.items()
              if window_start <= y <= deal.BUYER_FORECAST_BASE_YEAR}
    blocking = [c for c in run_all_checks(window) if not c.passed and c.kind == "hard"]

    if blocking:
        print(f"\nCANNOT RUN: {len(blocking)} hard failure(s) inside the driver window "
              f"FY{window_start}-FY{deal.BUYER_FORECAST_BASE_YEAR}. These are not "
              f"historical curiosities -- the forecast is derived from exactly these "
              f"years, so a structural break here propagates into every number "
              f"downstream:")
        for c in blocking:
            print(f"  HARD FAIL  {c.name}: {c.detail}")
        return 1
    if hard_fails:
        print(f"\n{len(hard_fails)} hard failure(s), all OUTSIDE the driver window "
              f"FY{window_start}-FY{deal.BUYER_FORECAST_BASE_YEAR}. They are real gaps "
              f"in the deep history and are reported rather than suppressed, but they "
              f"do not touch the years this model derives from, so they do not block "
              f"the run. A failure inside the window does.")

    large_soft = [c for c in soft_fails if c.diff is not None and abs(c.diff) > 5e9]
    if large_soft:
        print(f"\n{len(large_soft)} soft warning(s) exceed $5bn -- too large for the "
              f"routine FX/restricted-cash noise these checks normally flag. A gap this "
              f"size usually means a real corporate action (divestiture, spinoff, major "
              f"acquisition) moved something through the balance sheet or cash flow "
              f"statement that this schema doesn't have a line for -- not a bug in the "
              f"check, but not safe to wave through either:")
        for c in large_soft:
            print(f"  LARGE  {c.name}: diff ${c.diff / 1e9:+.1f}bn -- {c.detail[:100]}")

    year_gaps = [y for y in range(min(years), max(years)) if y not in years]
    if year_gaps:
        print(f"\nGAP IN THE YEAR SEQUENCE: {year_gaps} missing from an otherwise "
              f"continuous run {min(years)}-{max(years)}. A full missing year -- not a "
              f"single dropped field -- usually means either a genuine filing gap or an "
              f"XBRL tag transition year where none of this schema's tag fallbacks "
              f"matched at all. Worth a direct look at that year's 10-K before trusting "
              f"any driver whose lookback window spans across the gap.")

    print()

    base_year = deal.BUYER_FORECAST_BASE_YEAR
    if base_year not in years:
        print(f"\nCANNOT RUN: base year FY{base_year} is not in the historical table "
              f"{years}. The base year is not a tuning knob -- see "
              f"BUYER_FORECAST_BASE_YEAR_RATIONALE.")
        return 1
    print(f"\nDeriving drivers -- {deal.BUYER_DRIVER_LOOKBACK_YEARS}yr lookback ending "
          f"FY{base_year} (NOT FY{max(years)}, the latest available: J&J's post-2022 "
          f"results already consolidate Abiomed, so forecasting 'standalone' from them "
          f"would double-count the target). "
          f"Registry overrides: {profile.overrides or 'none'}")
    print(f"  Base-year rationale: {deal.BUYER_FORECAST_BASE_YEAR_RATIONALE[:240]}...")

    # The base year is the single most load-bearing choice in this model, and it was
    # silently wrong until Trellis commit 1b61d95. J&J's fiscal years end on the Sunday
    # nearest 31 December, so FY2020-FY2022 all closed in early January; keying the
    # table by the calendar year of period_end filed each of them one year late, and
    # bucket "2022" actually held the period ending 2022-01-02 -- J&J's FY2021. The
    # rationale below was carefully argued and the data underneath it was off by one,
    # with nothing failing. Printing the actual period end is the cheapest way to make
    # that class of error impossible to repeat: the label is an assertion, the date is
    # evidence.
    base_end = None
    for o in obs.get("revenue", []):
        if o.fiscal_period == "FY" and o.period_end and \
                fiscal_year_key(o.period_end) == base_year:
            base_end = max(base_end or o.period_end, o.period_end)
    if base_end is None:
        print("  ! Could not recover a period end for the base year -- the bucket "
              "label cannot be verified against a filing date. Do not trust the "
              "forecast until this is resolved.")
        return 1

    close = date.fromisoformat(deal.TERMS.closed)
    stub_days = (date.fromisoformat(base_end) - close).days
    print(f"  Base-year period END: {base_end} (verified from the filing, not inferred "
          f"from the bucket label)")
    # Two-sided, and the lower bound matters as much as the upper. The upper bound
    # catches a base year that has swallowed the target. The LOWER bound catches the
    # bug that actually happened: under the old keying, bucket 2022 held the period
    # ending 2022-01-02 -- J&J's FY2021, a full fiscal year further from the deal than
    # the rationale intended. A one-sided "is it pre-acquisition" test calls that
    # perfectly fine, because it is pre-acquisition; it is just the WRONG pre-
    # acquisition year. Anything closing more than roughly two quarters after the base
    # year ended means a whole fiscal year is being skipped.
    if stub_days < -200:
        print(f"  ! Closed {-stub_days}d AFTER this fiscal year ended. That is roughly a "
              f"full fiscal year of distance, not a stub: a year that should be in the "
              f"base is being skipped, which is exactly what a mis-keyed table looks "
              f"like. Verify the period end above against the filing before rerunning.")
        return 1
    if stub_days < 0:
        print(f"  Closed {-stub_days}d AFTER this fiscal year ended -- the base year is "
              f"entirely pre-acquisition, and close enough to the deal to be the right "
              f"one.")
    elif stub_days <= 45:
        print(f"  Closed {stub_days}d before this fiscal year ended -- a {stub_days}-day "
              f"stub of the target sits inside the base year. J&J called 2022's impact "
              f"immaterial; at this size that holds.")
    else:
        print(f"  ! Closed {stub_days}d before this fiscal year ended. That is too much "
              f"of the target inside a 'standalone' base year -- the forecast would "
              f"partly double-count what the model then adds back.")
        return 1
    drivers = derive_drivers_from_history(
        built.table, base_year=base_year,
        lookback_years=deal.BUYER_DRIVER_LOOKBACK_YEARS,
        overrides=profile.overrides or None)
    if drivers.assumptions:
        print(f"Drivers with no clean historical derivation "
              f"({len(drivers.assumptions)}) -- these are Trellis's own flagged gaps, "
              f"not silently defaulted:")
        for note in drivers.assumptions:
            print(f"  {note}")

    # Trellis's own `overrides` parameter only supports interest_rate, debt_repayment,
    # and revolver_limit -- it has no mechanism for overriding an income-statement ratio
    # driver like tax_rate (confirmed against trellis/forecast.py directly). Applied
    # after derivation instead, on the frozen Drivers dataclass, with the same
    # overrides_applied bookkeeping Trellis itself uses -- so this reads as a normal
    # sourced override in every downstream printout, not a silent patch.
    print(f"\nGAAP tax_rate as derived from history: {drivers.tax_rate:.2%}")
    print(f"Overriding to {deal.BUYER_TAX_RATE_OVERRIDE.value:.2%} -- J&J's own "
          f"net-income-derived GAAP rate is contaminated by the same talc-litigation "
          f"and Kenvue-exchange volatility distorting margin generally (see "
          f"deallab.deals.jnj_abiomed module docstring). Reason: "
          f"{deal.BUYER_TAX_RATE_OVERRIDE.citation[:200]}...")
    drivers = dataclasses.replace(
        drivers, tax_rate=deal.BUYER_TAX_RATE_OVERRIDE.value,
        overrides_applied=drivers.overrides_applied + (
            (f"tax_rate = {deal.BUYER_TAX_RATE_OVERRIDE.value:.4f} -- applied outside "
             f"Trellis's own overrides mechanism (not supported for this driver), see "
             f"deallab.deals.jnj_abiomed.BUYER_TAX_RATE_OVERRIDE"),))

    forecast = run_forecast(built.table, base_year=base_year, drivers=drivers, years=5)
    forecast_years = sorted(forecast)
    print(f"\nForecast years: {forecast_years}")

    print("\nWhat the raw historical table actually contains, for the base year "
          "(so you can see whether share count is in here or needs sourcing "
          "separately -- Trellis's schema is statement line items, not per-share data):")
    for k in sorted(built.table[base_year]):
        print(f"  {k}")

    # --- Cache the FULL historical table, raw dollars, Trellis-native -----------------
    # Written so diagnose_jnj_kenvue.py (and any future analysis) can run against this
    # data without hitting SEC EDGAR again -- one network trip, reused locally after.
    hist_path = ROOT / "data" / "jnj_historical.json"
    hist_path.parent.mkdir(exist_ok=True)
    hist_path.write_text(json.dumps({str(y): built.table[y] for y in years}, indent=2))
    print(f"\nWrote {hist_path.relative_to(ROOT)} (full historical table, raw dollars, "
          f"for local re-analysis without refetching)")

    # --- Convert to DealLab's $mm convention and write the buyer-side input file -----
    out = {}
    for i, y in enumerate(forecast_years, start=1):
        row = forecast[y]
        out[str(i)] = {
            "fiscal_year": y,
            "revenue_mm": row["revenue"] / 1e6,
            "operating_income_mm": row["operating_income"] / 1e6,
            "net_income_mm": row["net_income"] / 1e6,
            "depreciation_amortisation_mm": row.get("depreciation_amortization", 0.0) / 1e6,
        }

    out_path = ROOT / "data" / "jnj_standalone_forecast.json"
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\nWrote {out_path.relative_to(ROOT)}")
    print("\nStill needed separately: J&J's diluted weighted-average share count is not "
          "in Trellis's schema (it covers statement line items, not per-share data) -- "
          "source it from the same 10-K's EPS footnote or cover page, the same way "
          "TARGET_SHARES_OUTSTANDING was sourced for Abiomed.")
    return 1 if hard_fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
