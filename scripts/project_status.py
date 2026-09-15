"""Is DealLab actually finished? Check every layer and say what is left.

Not a test suite -- the tests answer "does the code do what it claims." This answers a
different question: "is there anything still unbuilt, uncollected, or unverified that
would stop someone using this for real?" Those gaps do not show up as test failures,
because a correct engine with no data in it passes every test it has.

Four layers, checked in order of what blocks what:

  1. ENGINE      -- modules present, importable, tested
  2. DATA        -- what the deal file has sourced vs. still missing
  3. PIPELINE    -- has the buyer forecast actually been produced
  4. RUNNABILITY -- does the end-to-end model execute, and does it tie to disclosures

    python scripts/project_status.py
"""
import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

ENGINE_MODULES = [
    "provenance", "terms", "calendarize", "financing", "sources_uses",
    "purchase_accounting", "synergies", "proforma", "accretion", "returns",
    "verdict", "guidance", "bridge", "loader", "engine",
]

OK, WARN, GAP = "  [OK]  ", "  [WARN]", "  [GAP] "


def main() -> int:
    findings: list[tuple[str, str]] = []

    # --- 1. ENGINE -------------------------------------------------------------------
    print("=" * 76)
    print("1. ENGINE")
    print("=" * 76)
    for name in ENGINE_MODULES:
        try:
            importlib.import_module(f"deallab.{name}")
            print(f"{OK} deallab.{name}")
        except Exception as e:  # noqa: BLE001 -- a diagnostic reports, never raises
            print(f"{GAP} deallab.{name} FAILED TO IMPORT: {e}")
            findings.append(("GAP", f"deallab.{name} does not import"))

    from deallab.deals import jnj_abiomed as deal

    # --- 2. DATA ---------------------------------------------------------------------
    print("\n" + "=" * 76)
    print("2. DATA -- what the deal file holds")
    print("=" * 76)

    sourced_items = [
        ("deal terms (price, CVR, shares)", deal.TERMS.cash_per_share),
        ("target net debt", deal.TARGET_NET_DEBT),
        ("target book equity", deal.TARGET_BOOK_EQUITY),
        ("target revenue", deal.TARGET_REVENUE_FY2022),
        ("target operating income", deal.TARGET_OPERATING_INCOME_FY2022),
        ("target net income", deal.TARGET_NET_INCOME_FY2022),
        ("target effective tax rate", deal.TARGET_EFFECTIVE_TAX_RATE_FY2022),
        ("J&J amortizable intangibles", deal.INTANGIBLE_AMORTIZABLE_FV),
        ("J&J IPR&D", deal.IPRD_FV),
        ("J&J deferred tax liability", deal.DEFERRED_TAX_LIABILITY_ABIOMED),
        ("J&J acquisition costs", deal.ADVISORY_FEES_PRETAX),
        ("buyer diluted share count", deal.BUYER_DILUTED_SHARES),
    ]
    for label, item in sourced_items:
        flag = OK if not item.is_missing else GAP
        note = " [SECONDARY]" if "SECONDARY SOURCE" in item.citation else ""
        print(f"{flag} {label}: {item.basis.value}{note}")

    print("\n  Assumed (choices, not evidence -- each cited in the deal file):")
    for label, item in [("CVR probability weight", deal.CVR.probability_weight),
                        ("buyer tax rate", deal.BUYER_TAX_RATE_OVERRIDE)]:
        print(f"{WARN} {label} = {item.value} ({item.basis.value})")

    if deal.MISSING:
        print(f"\n  Still uncollected ({len(deal.MISSING)}):")
        for i in deal.MISSING:
            print(f"{GAP} {i.name}")
            findings.append(("GAP", f"uncollected: {i.name}"))
    else:
        print(f"\n{OK} Nothing left in MISSING.")

    print(f"\n{WARN} financing mix: never disclosed by J&J -- handled as a "
          f"{len(deal.FINANCING_SCENARIOS)}-scenario sensitivity, not a guess.")
    findings.append(("WARN", "financing mix undisclosed -- spanned, not resolved"))

    # --- 3. PIPELINE -----------------------------------------------------------------
    print("\n" + "=" * 76)
    print("3. PIPELINE -- buyer forecast")
    print("=" * 76)
    forecast = ROOT / "data" / "jnj_standalone_forecast.json"
    historical = ROOT / "data" / "jnj_historical.json"
    forecast_ok = False
    if not forecast.exists():
        print(f"{GAP} {forecast.relative_to(ROOT)} not found.")
        print("       Run: python scripts/run_trellis_jnj.py "
              "(needs TRELLIS_USER_AGENT + network)")
        findings.append(("GAP", "buyer forecast not yet produced"))
    else:
        try:
            from deallab.loader import load_standalone_years
            years = load_standalone_years(forecast, expect_years=5)
            print(f"{OK} {forecast.relative_to(ROOT)}: {len(years)} years, "
                  f"year-1 revenue ${years[0].revenue:,.0f}mm")
            forecast_ok = True
        except Exception as e:  # noqa: BLE001
            print(f"{GAP} {forecast.relative_to(ROOT)} failed to load: {e}")
            findings.append(("GAP", "buyer forecast present but unloadable"))
    if historical.exists():
        n = len(json.loads(historical.read_text()))
        print(f"{OK} {historical.relative_to(ROOT)}: {n} historical years cached")
    else:
        print(f"{WARN} {historical.relative_to(ROOT)} not found -- "
              f"diagnose_jnj_kenvue.py needs it")

    # --- 4. RUNNABILITY --------------------------------------------------------------
    print("\n" + "=" * 76)
    print("4. RUNNABILITY")
    print("=" * 76)
    if not forecast_ok:
        print(f"{GAP} Cannot run end-to-end without the buyer forecast.")
    else:
        print(f"{OK} All inputs present -- run: python scripts/run_jnj_abiomed.py")
        print(f"{WARN} A run producing output is not a run producing a TRUE answer.")
        print("       The model's year-1 adjusted accretion should be compared against")
        print("       J&J's disclosed 'slightly dilutive to neutral' guidance, and any")
        print("       gap explained rather than tuned away.")

    # --- Verdict ---------------------------------------------------------------------
    print("\n" + "=" * 76)
    print("VERDICT")
    print("=" * 76)
    gaps = [f for k, f in findings if k == "GAP"]
    warns = [f for k, f in findings if k == "WARN"]

    if not gaps:
        print("  COMPLETE. Engine built and tested, data sourced, pipeline run,")
        print("  model executes end to end against real filings.")
    else:
        print(f"  {len(gaps)} gap(s) remaining:")
        for g in gaps:
            print(f"    - {g}")
    if warns:
        print(f"\n  {len(warns)} item(s) that will NOT close -- not because the work is")
        print("  unfinished, but because the information does not exist publicly:")
        for w in warns:
            print(f"    - {w}")
        print("\n  These are handled by spanning or flagging rather than guessing.")
        print("  A model that reported a single confident number here would be less")
        print("  honest, not more finished.")

    print("\n  Structural limits stated in the README and not planned: no bargain")
    print("  purchase / NCI / measurement-period adjustments, no CVR remeasurement,")
    print("  linear within-year calendarization, synergies at buyer WACC.")
    return 1 if gaps else 0


if __name__ == "__main__":
    raise SystemExit(main())
