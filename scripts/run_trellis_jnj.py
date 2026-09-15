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
    if hard_fails:
        print("\nHard failures mean the historical table has a real structural problem "
              "(balance sheet doesn't balance, etc.) -- read these before forecasting "
              "off this table. Continuing anyway so you can inspect the output, but "
              "treat anything downstream as suspect until these are resolved.")

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
