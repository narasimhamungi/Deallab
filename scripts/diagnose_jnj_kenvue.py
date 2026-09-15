"""Does J&J's 5-year driver lookback straddle the Kenvue spinoff? Show the numbers.

run_trellis_jnj.py's default 5-year lookback (FY2021-2025) covers the period J&J spun
off its consumer health business (Kenvue) in 2023 -- roughly $15bn of J&J's then ~$95bn
revenue, by public reporting at the time. A revenue_growth CAGR or margin average that
blends pre-spinoff (three-segment) and post-spinoff (two-segment: Pharmaceutical +
MedTech) years isn't measuring organic growth or margin trend at all -- it's measuring
portfolio composition change, and using it to forecast the POST-spinoff company (the one
actually relevant to the Abiomed deal, since Abiomed sits inside MedTech) would silently
bake a one-time discontinuity into a "growth rate."

This script does not assume that's what happened. It shows the actual revenue and net
income series, year by year, so the discontinuity (if there is one) is visible rather
than inferred -- and it re-derives drivers under a few different lookback choices so the
sensitivity to the window is a measured comparison, not a guess.

Reads data/jnj_historical.json -- no network needed. Run run_trellis_jnj.py first if
that file doesn't exist yet.

    python scripts/diagnose_jnj_kenvue.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    try:
        from trellis.forecast import derive_drivers_from_history
    except ImportError as e:
        print(f"Trellis is not installed: {e}")
        return 1

    hist_path = ROOT / "data" / "jnj_historical.json"
    if not hist_path.exists():
        print(f"{hist_path.relative_to(ROOT)} not found -- run scripts/run_trellis_jnj.py "
              f"first (it writes this file as a side effect of the live fetch).")
        return 1

    raw = json.loads(hist_path.read_text())
    table = {int(y): row for y, row in raw.items()}
    years = sorted(table)

    print(f"Historical years available: {years}\n")

    print("REVENUE AND NET INCOME BY YEAR ($bn) -- look for a level shift, not a trend")
    print("-" * 72)
    print(f"  {'Year':<6}{'Revenue':>12}{'YoY':>10}{'Net income':>14}{'Margin':>10}")
    prior_rev = None
    for y in years:
        row = table[y]
        rev = row.get("revenue")
        ni = row.get("net_income")
        if rev is None:
            print(f"  {y:<6}{'(missing revenue)':>12}")
            continue
        yoy = f"{(rev / prior_rev - 1):+.1%}" if prior_rev else "--"
        margin = f"{ni / rev:.1%}" if ni is not None else "--"
        ni_str = f"{ni / 1e9:.1f}" if ni is not None else "--"
        print(f"  {y:<6}{rev / 1e9:>11.1f}{yoy:>10}{ni_str:>14}{margin:>10}")
        prior_rev = rev

    print("\n  A double-digit-percent one-year revenue DROP with no corresponding")
    print("  operating-margin collapse is the signature of a divestiture, not a bad")
    print("  year -- the business that left didn't stop being profitable, it just")
    print("  stopped being J&J's. Read the year(s) around any such drop against the")
    print("  Kenvue spinoff timeline (completed August 2023) before trusting a CAGR")
    print("  that spans across it.")

    all_years = set(years)
    expected = set(range(min(years), max(years) + 1))
    gaps = sorted(expected - all_years)
    print(f"\nMissing years in the sequence: {gaps or 'none'}")

    print("\n" + "=" * 72)
    print("DRIVER SENSITIVITY TO THE LOOKBACK WINDOW")
    print("=" * 72)
    base_year = max(years)
    windows = [
        ("Default 5yr lookback", {"lookback_years": 5}),
        ("3yr lookback (mostly post-spinoff)", {"lookback_years": 3}),
        ("2yr lookback (fully post-spinoff)", {"lookback_years": 2}),
    ]
    # Also try explicitly excluding the spinoff year itself and the year before it,
    # if they're in range -- a direct test rather than just shortening the window.
    spinoff_candidates = {y for y in (2022, 2023) if y in all_years}
    if spinoff_candidates:
        windows.append((f"5yr lookback, excluding {sorted(spinoff_candidates)}",
                        {"lookback_years": 5, "exclude_years": spinoff_candidates}))

    results = []
    for label, kwargs in windows:
        try:
            d = derive_drivers_from_history(table, base_year=base_year, **kwargs)
            results.append((label, d))
        except Exception as e:  # noqa: BLE001 -- diagnostic script, show any failure
            print(f"\n{label}: FAILED -- {e}")

    print(f"\n  {'Window':<40}{'rev growth':>12}{'gross margin':>14}{'tax rate':>10}")
    for label, d in results:
        print(f"  {label:<40}{d.revenue_growth:>12.2%}{d.gross_margin:>14.2%}"
              f"{d.tax_rate:>10.2%}")

    if len(results) >= 2:
        spread = max(r[1].revenue_growth for r in results) - min(r[1].revenue_growth for r in results)
        print(f"\n  Revenue growth spread across windows: {spread:.2%}")
        if spread > 0.03:
            print("  >3 percentage points of spread from window choice alone is large --")
            print("  the forecast is materially sensitive to a decision this script can")
            print("  surface but not make for you. Pick the window deliberately, state")
            print("  which one and why, and treat the choice itself as a disclosed")
            print("  assumption in DealLab's own provenance system -- not a default.")
        else:
            print("  Spread is small -- the window choice doesn't appear to be doing")
            print("  much work here. Weakens (doesn't eliminate) the spinoff-distortion")
            print("  concern; the revenue table above is still the primary evidence.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
