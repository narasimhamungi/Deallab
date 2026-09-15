# Running DealLab

## Install

DealLab consumes ValuationLab as a package, which consumes Trellis the same way.

```bash
pip install git+https://github.com/narasimhamungi/trellis.git
pip install --no-deps git+https://github.com/narasimhamungi/valuationlab.git
pip install -e .
pip install pytest ruff
```

`--no-deps` on ValuationLab is deliberate: it declares Trellis as a git dependency, and
installing Trellis first from the same source avoids pip resolving the two against each
other. Nothing is skipped — both packages are present.

## Order of operations

**1. Check what is collected.**

```bash
python scripts/check_inputs.py
```

Exits non-zero while inputs are outstanding, and prints for each one the filing that
contains it. Also prints the derived reconciliation checks and the disclosed guidance the
model will be measured against.

**2. Collect the outstanding inputs.** Read the filings listed. Enter each as a
`sourced()` input in `src/deallab/deals/jnj_abiomed.py`, replacing the corresponding
`unsourced()` entry and carrying the citation across. Do not enter a plausible number
tagged `assumed()` for something a filing actually discloses — that is how a researchable
fact hides in the assumption register permanently.

**3. Run J&J's standalone forward through Trellis.**

```bash
export TRELLIS_USER_AGENT="YourName your-email@example.com"   # SEC requires this
python scripts/run_trellis_jnj.py
```

Fetches J&J's real filings via SEC EDGAR (CIK 200406, already validated in Trellis's
registry), runs the ingest → historical table → structural checks → 5-year forecast
pipeline, prints every diagnostic along the way (FYE collisions, derived gap-fills,
hard/soft check failures, drivers Trellis couldn't cleanly derive, any year missing from
the sequence, any soft check discrepancy over $5bn), and writes two files: the full
historical table to `data/jnj_historical.json` (raw dollars, Trellis-native, so later
analysis doesn't need to refetch), and the 5-year forecast to
`data/jnj_standalone_forecast.json` — already converted to DealLab's $mm convention,
since Trellis itself reports raw as-filed dollars and the conversion happens once,
deliberately, at this boundary rather than being left for a caller to get wrong later.

**Needs outbound network access to `data.sec.gov`.** If you're running this from an
environment with restricted egress (a sandboxed container, a locked-down CI runner),
it will fail with a 403 regardless of the user-agent — that's the network boundary
blocking the request, not an ingestion bug. Run it somewhere with normal internet
access.

J&J's diluted share count is not in Trellis's schema (statement line items only, no
per-share data) — source it separately from the same 10-K's EPS footnote, the same way
`TARGET_SHARES_OUTSTANDING` was sourced for Abiomed.

**3b. Check the lookback window against the Kenvue spinoff.** J&J spun off its consumer
health business (Kenvue) in August 2023. The default 5-year lookback in step 3 can
straddle that, blending a three-segment company's history with a two-segment one's into
a single "growth rate" that measures portfolio composition change, not organic trend --
material specifically because the post-spinoff company (Pharmaceutical + MedTech) is the
one actually relevant to this deal.

```bash
python scripts/diagnose_jnj_kenvue.py
```

Reads the cached `data/jnj_historical.json` from step 3 -- no network needed. Prints
revenue and net income by year (so a spinoff-shaped level shift is visible directly, not
inferred), flags any missing year, and re-derives drivers under a few different lookback
windows so the sensitivity to that choice is measured rather than assumed. If the spread
across windows is small, the concern is largely moot. If it's large, pick a window
deliberately, state which one and why in the fixture, and record the choice as a
disclosed assumption -- the same provenance discipline as everything else in this repo,
not a default `derive_drivers_from_history(table, base_year)` call left unexamined.

**4. Get the target standalone value from ValuationLab.** Build the method ranges, call
`triangulate`, then pass the resulting `Conclusion` to `deallab.bridge.standalone_value`.
If it comes back `fit=False`, that is a finding: the economic lens will report that the
premium cannot be measured rather than inventing a benchmark.

**5. Run the model.**

```python
from deallab import engine
result = engine.run(model)
print(result.format())
verdict = engine.build_verdict(result, standalone_value=..., standalone_basis=...,
                               synergy_npv=..., wacc=...)
print(verdict.format())
```

**6. Check against guidance.**

```python
from deallab.guidance import check_range, check_point, GuidanceReport
from deallab.deals import jnj_abiomed as deal

report = GuidanceReport((
    check_range("Year 1 adjusted EPS", "adjusted",
                deal.GUIDANCE["year_one_adjusted_eps"],
                *deal.GUIDANCE_YEAR_ONE_BOUNDS,
                modelled=result.accretion[0].adjusted_pct),
    check_point("2024 adjusted accretion", "adjusted", deal.GUIDANCE["2024_adjusted_eps"],
                deal.GUIDANCE_2024_ACCRETION_USD,
                modelled=result.accretion[1].adjusted_delta_eps, tolerance=0.02),
))
print(report.format())
```

If the model misses guidance, do not adjust an input until it matches. Identify which
assumption drives the gap and state the disagreement. A model tuned to reproduce guidance
can no longer test it.

## Mechanics demo

```bash
python scripts/demo_mechanics.py
```

Runs end to end on invented numbers. Useful for seeing the output shape before the real
inputs are collected. It says so on screen; nothing in it refers to a real transaction.

## Tests

```bash
python -m pytest -q        # 176 tests
```

`tests/test_bridge.py` runs against the real installed ValuationLab and Trellis, not
mocks, and skips cleanly if they are absent.
