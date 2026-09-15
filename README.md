# DealLab

An M&A transaction model that answers whether an acquisition creates value for the
buyer — and reports the **accounting answer and the economic answer separately**, because
they are different questions and a deal can pass one while failing the other.

Built on [ValuationLab](https://github.com/narasimhamungi/valuationlab), which is built
on [Trellis](https://github.com/narasimhamungi/trellis). DealLab consumes ValuationLab as
an installed package: fundamentals are ingested from SEC EDGAR XBRL once, through one
pipeline, and each layer inherits that provenance rather than re-sourcing it.

**Status:** engine complete and tested (173 tests). The J&J/Abiomed deal file is sourced
from the 8-Ks and 10-Ks on both sides of the deal — target fundamentals from Abiomed's
own filings, J&J's own headline purchase price allocation (goodwill $11.1bn, amortizable
intangibles $6.6bn, IPR&D $1.1bn, and a $1.8bn deferred tax liability explicitly
attributed to this acquisition by name) from J&J's 10-K — and carries the disclosed EPS
guidance the model will be checked against. The CVR's probability weight is now a cited,
reasoned estimate rather than a blocking unknown, and the buyer-side forecast's two
most contestable drivers (tax rate, revenue growth window) are now deliberate, cited
decisions rather than whatever Trellis's defaults would have produced. Three items
remain: the CVR's specific *booked* fair value (vs. the estimate now in use), J&J's
actual financing mix, and one mechanical pipeline run (J&J's own Trellis forecast, with
its methodology now resolved). The model refuses to run until they are collected, and
names the filing that contains each one. See
[Current state](#current-state).

---

## The problem

Almost every merger model reports one number — accretion or dilution to EPS — and treats
it as the verdict. It is not a verdict. Accretion/dilution is a function of relative P/E
and funding cost. A buyer trading at 25x can acquire a target at 15x with debt and show
accretion having created nothing, and will book the resulting goodwill impairment three
years later. The number that gets presented is the one least able to answer the question
being asked.

Three further failures are near-universal in merger-model templates:

- **Cash is treated as free.** Balance-sheet cash spent on an acquisition stops earning
  interest. At current short rates, on a multi-billion drawdown, that foregone income is
  worth cents of EPS — enough on its own to flip a marginal deal.
- **Run-rate synergies land in year one.** Announced synergies are quoted at full
  realisation in year three or four. Dropping them into year one manufactures day-one
  accretion that will not occur.
- **The price is taken as given.** With no standalone valuation to net against, a
  template can compute what the price does to EPS but never whether the price was
  defensible.

## Why it matters

For an IB, corporate development or transaction advisory seat, the interviewable skill is
not building the model — it is knowing what the model cannot tell you. "The deal is 3%
accretive" is a starting point. "It is 3% accretive on adjusted EPS, 6% dilutive on GAAP,
and the price requires $340mm of annual synergy to hold EPS flat against $180mm
management has identified" is an analysis. This repo is built so the second version is the
only one it can produce.

## What was built

Fourteen modules. The four that make this more than a template are marked.

| Module | Responsibility |
|---|---|
| `provenance.py` | Demonstrated / Sourced / Assumed, carried forward from Trellis, plus an assumption register printed **before** any result |
| `terms.py` | Consideration structure including **contingent value rights** at probability-weighted fair value under ASC 805 |
| `calendarize.py` | **Fiscal-year alignment** for mismatched buyer/target FYEs, and stub-period handling in the year of close |
| `financing.py` | Debt tranches (bullet and amortising, interest on average balance), cash drawdown, and **foregone interest income** |
| `sources_uses.py` | Sources & uses with an enforced balance check, and the expensed-vs-capitalised fee split kept apart |
| `purchase_accounting.py` | ASC 805 allocation, goodwill as residual, DTL on a non-deductible step-up (or the buyer's own disclosed figure where it exists), finite- and indefinite-lived intangibles, inventory step-up unwind |
| `synergies.py` | Phased, costed and discounted; revenue synergies margined and isolated so the case can be re-run without them; dis-synergies supported |
| `proforma.py` | The combination presented as a **net income bridge**, GAAP and adjusted computed in one pass and kept separate; eliminates the target's own interest where its debt is repaid |
| `accretion.py` | GAAP and adjusted separately, **breakeven synergy solve**, and EPS attribution by driver |
| `returns.py` | IRR (bracketed bisection, refuses rather than returning a plausible wrong root) and MOIC against the buyer's cost of capital |
| `verdict.py` | **The two lenses, structurally non-mergeable** — no combined score exists on the result type |
| `guidance.py` | The model checked against what the buyer actually disclosed |
| `bridge.py` | The seam to ValuationLab and Trellis, honouring upstream disqualifications |
| `loader.py` | Reads a Trellis-produced forecast JSON into engine inputs, refusing raw-dollar units, year gaps, and NaN rather than coercing them |
| `engine.py` | End-to-end orchestration preserving every stage's output |

### The four things a generic merger model cannot do

**1. Breakeven synergies.** Inverts the accretion arithmetic: what annual pre-tax synergy
is required to hold EPS flat? This converts an opinion ("management says $X") into a
testable claim ("the price requires $Y"). If required exceeds identified, the deal rests
on benefits nobody has named, and the model says so in those words.

**2. The unexplained premium.** Price paid, less the target's standalone value, less the
present value of identified synergies. Whatever remains is what the buyer is paying for
benefits that have not been articulated. A template cannot produce this because it has no
standalone valuation to net against.

The mechanism is built to consume ValuationLab: `bridge.standalone_value` takes a
ValuationLab `Conclusion`, honours its anchor disqualifications, and returns `fit=False`
rather than reaching past them — and `verdict.build_economic_verdict` then **declines to
state a premium** instead of using a number ValuationLab already flagged as unreliable.
That path is tested against the live installed package.

**What the J&J/Abiomed run actually uses is Abiomed's unaffected market EV**, not a
ValuationLab run. Stated plainly because the distinction matters: running ValuationLab on
Abiomed needs a cardiovascular-device peer set and DCF inputs that have not been
collected, and inventing them to fill the slot would be worse than using a real
pre-announcement market price. The market anchor is honest and sourced; it is not an
intrinsic valuation, and the output says so at the point of use.

**3. Contingent consideration.** A CVR worth up to 9% of the headline price is not a
rounding detail, and neither zero nor the maximum is the right carrying value. Recognised
at probability-weighted acquisition-date fair value, with the probability visible in the
assumption register where it can be attacked.

**4. Two verdicts that refuse to merge.** `DealVerdict` has no `score`, no `overall`, no
weighted blend — and a test asserts those attributes do not exist. It names the quadrant
instead. Accretive-but-unexplained-premium is identified in the output as the shape of a
value-destroying acquisition: successful in guidance, a goodwill impairment later.

## Data & tools

- **Fundamentals** — SEC EDGAR company-facts XBRL via Trellis. J&J (CIK 200406) is
  already in the Trellis registry and validated.
- **Standalone valuation** — ValuationLab, consumed as a package. Not used to set the
  price; used as the benchmark the price is measured against.
- **Deal data** — read directly from the acquirer's 8-K exhibits on EDGAR. Deal terms are
  not in XBRL and not available free via API.
- **Precedent multiples** — one cited deal at a time. `bridge.precedent_check` raises a
  `TypeError` if handed a list, because ValuationLab measured that pooling is wrong:
  J&J/Actelion at 12.3x EV/Revenue and BMS/Celgene at 4.8x sit in the same tier, 2.5x
  apart.
- **Testing** — pytest, 173 tests. Expected values are computed by hand in the test and
  compared, not snapshotted from the code's own output.

## Methodology

Ordering is fixed and each stage feeds the next: terms → consideration → allocation →
step-up charges → pro-forma bridge → accretion → returns → the two verdicts. The
assumption register threads through every stage and prints first, before any result.

The chosen deal is **Johnson & Johnson / Abiomed**, announced 1 November 2022, closed
22 December 2022. $380.00 per share in cash plus a non-tradeable CVR of up to $35.00 per
share on three milestones; stated enterprise value approximately $16.6bn.

Three reasons this deal rather than a hypothetical:

1. **It continues a proven thread.** ValuationLab established that J&J cannot be valued
   as one company — pharma peer dispersion widens with more peers (2.5x to 4.7x),
   structural rather than sample noise — while the MedTech segment values cleanly on its
   own peer group. Abiomed is a real acquisition into exactly that segment, so the target
   valuation DealLab consumes is one ValuationLab would stand behind.

2. **It has an answer key.** J&J guided the transaction as slightly dilutive to neutral
   to adjusted EPS in year one *including financing impact*, accretive by approximately
   $0.05 in 2024, and increasingly accretive thereafter. The model's job is to land near
   that and explain any gap. A hypothetical is internally consistent and unfalsifiable;
   this one can be wrong.

3. **It has two features a template cannot handle.** The CVR, and the disclosed decision
   to run Abiomed as a **standalone business** within J&J MedTech — an explicit choice to
   forgo integration cost synergies. Assuming generic percentage-of-opex cost synergies
   here would contradict a disclosed fact, which is why `synergies.py` supports
   dis-synergies and why the deal file says so.

A fourth, quieter reason the deal is a good test: Abiomed reported on a **March fiscal
year end** against J&J's December. Combining Abiomed's FY2022 (April 2021 – March 2022)
into J&J's calendar 2022 is wrong by a nine-month offset, which on a target growing ~22%
a year misstates contributed revenue by roughly a sixth. That is what `calendarize.py`
exists for, and most merger models do not have the module at all.

## Key findings

Findings from the model **run** are pending the four remaining J&J-side inputs. What
sourcing the target's own fundamentals already established:

- **A real, unresolved $470mm gap.** With Abiomed's actual sourced net cash ($1,004.2mm,
  30 Jun 2022, corroborated word-for-word by Abiomed's own press release: "no debt") and
  the actual disclosed share count (45.091184mm), upfront-only derived EV is $16,130mm
  against J&J's stated "approximately $16.6 billion" — a 2.8% shortfall, material, not
  rounding. Two readings are laid out in the deal file, neither adopted without more
  evidence: the stated figure is most likely a rounded PR number describing cash
  consideration only; less plausibly, it could implicitly reflect the CVR at a specific
  ~30% probability weight, which would close the gap almost exactly by coincidence. The
  model states the gap and both readings rather than picking one to force a reconciliation.
- **A citation error caught by re-deriving it, not by re-reading it.** An earlier pass
  pointed the balance-sheet pull at Abiomed's 10-Q for the quarter ended 30 September
  2022, calling it "the last balance sheet before announcement." It was filed 3 November
  2022 — two days *after* the 1 November announcement. The actual last public balance
  sheet at signing is the 30 June 2022 10-Q. Corrected in the deal file, left visible
  rather than silently fixed, because reaching for the nearest-dated filing without
  checking it actually predates the trigger event is a realistic failure mode.
- **A real bug caught by a test.** The fiscal-overlap calculation returned the complement
  of the correct figure (9 months instead of 3), which would have inverted every
  calendarization weight. Caught because the test computed the expected value by hand from
  the Abiomed/J&J calendars rather than snapshotting the code's output.
- **A double-count caught by a linter.** `target_tax_rate` was accepted and never used —
  because the adjustment it belongs to was missing. Repaying the target's debt in sources
  & uses eliminates the target's own pre-deal interest expense, and leaving it in charges
  the same debt twice: once inside the target's contributed net income and again as new
  acquisition interest. Now booked, after tax at the target's rate, which is the one place
  that rate legitimately enters the combination.
- **The CVR is 9.2% of the upfront price** — large enough that carrying it at zero or at
  maximum both materially misstate the consideration, and therefore goodwill.
- **Target fundamentals tie exactly.** Pretax income ($190.560mm) less the tax provision
  ($54.055mm) equals reported net income ($136.505mm) to the dollar, and the effective
  rate (28.4%) is well above the 21% statutory rate because of a foreign pretax loss
  alongside a US pretax gain — a real cross-check a secondary-sourced figure never offered.
- **J&J's own restatement of its own headline number moved.** "Approximately $16.6
  billion" at announcement became "approximately $16.5 billion" in J&J's FY2024 10-K's
  retrospective description of the same deal — independent evidence, from the buyer's
  own filings, that the headline EV is an approximate PR figure rather than one meant
  to reconcile to the cent.
- **The two EV reconciliations disagree in a way worth keeping, not resolving.**
  Upfront-only, the derived EV sits $470mm (2.8%) BELOW J&J's stated $16.6bn. Once the
  CVR is included at an independently-estimated fair value ($781mm, from J&J's own
  contingent-consideration rollforward, not fitted to close this gap), the derived EV
  sits $312mm (1.9%) ABOVE it — inside this file's own 2% "ties" threshold. Suggestive
  that the stated EV reflects some CVR value after all; not proof, since the CVR weight
  behind it is itself a circumstantial estimate. Both numbers are printed, not just the
  one that happens to tie.
- **A deferred tax liability sourced by name.** J&J's own 10-K states a footnote total
  is "inclusive of the $1.8 billion deferred tax liability due to the acquisition of
  Abiomed" — explicit, unambiguous attribution, unlike the CVR estimate above, and the
  two are deliberately tagged at different confidence levels in the code rather than
  both being called "sourced."
- **J&J's own PPA sourced, not modelled.** Goodwill $11.1bn, amortizable intangibles
  $6.6bn at a 14-year weighted life (primarily in-market Impella products, one bucket —
  not split by sub-category as the fixture originally guessed the disclosure would be),
  and IPR&D $1.1bn indefinite-lived at 52%-70% probability of success. Two different
  measurement-period-adjustment figures appear across J&J's own filings ($0.1bn per the
  Q1 2023 10-Q, $0.2bn per the FY2024 10-K) — expected, not an error, since ASC 805
  true-ups accrue over the year following acquisition; the later, fuller figure is the
  one kept.
- **A wrong prediction, corrected by running the actual numbers instead of trusting the
  hypothesis.** Expected J&J's own historicals to show a clean revenue level-shift at the
  Kenvue spinoff (completed Aug 2023). They didn't — revenue dipped in FY2022, not
  FY2023, and grew every year after. What the real data showed instead was more useful:
  GAAP net margin swinging 17.8% → 26.5% → 22.4% → **15.8% (2024, the low point despite
  +11% revenue growth that year)** → 28.5%, decoupled from revenue entirely. J&J's own
  FY2024 10-K explains it directly — talc litigation charges swinging from $1.9bn of
  *income* (2022) to $6.6bn of *expense* (2023) to $4.7bn of expense (2024), plus a
  $0.4bn loss completing the Kenvue debt-for-equity exchange in 2024. That last item is
  also the most likely explanation for the $25.2bn FY2024 retained-earnings gap Trellis's
  own structural check had already flagged as too large for routine FX noise — a
  debt-for-equity exchange typically moves value through paid-in capital, not net income,
  which Trellis's RE-rollforward check has no line for. A real limitation of the check,
  not a bug in it.
- **Two forecast-driver decisions made deliberately, not defaulted.** (1) J&J's own
  *adjusted* effective tax rate is tight (15–17% across every disclosed quarter found)
  despite the *GAAP* rate — what Trellis derives from history — swinging 8%–17%
  year to year on the volatility above. Applied a 16% override on Trellis's own derived
  `Drivers` after the fact (`dataclasses.replace`), since Trellis's built-in `overrides`
  parameter only supports `interest_rate`, `debt_repayment`, and `revolver_limit` —
  confirmed directly against its source, not assumed — and has no mechanism for
  overriding an income-statement ratio driver at all. (2) Revenue growth ranged 3.34%
  to 8.52% across lookback windows tested — real sensitivity, not noise. Chose a 5-year
  window excluding 2022–2023, reasoned in two tiers of confidence: FY2023's mid-year
  Kenvue separation mechanically distorts that year's YoY comparison (direct, needs no
  further citation); FY2022's dip is plausibly COVID-vaccine runoff plus a strong-dollar
  year (labelled as this file's own inference, not a located citation). Also rejected the
  *highest-scoring* window (3yr, 8.52%) with a stated reason — it still partly reflects a
  bounce off FY2022's depressed base — rather than picking the most flattering number.

## Insight demonstrated

Knowing which question a number answers. Accretion/dilution answers "what happens to
reported EPS", not "did we pay too much", and the discipline that matters in a deal seat
is keeping the two apart under pressure to produce a single recommendation. The
architecture enforces it: there is no code path that produces a blended verdict, and the
assumption register prints before the answer so the reader sees what the conclusion rests
on before they see the conclusion.

## Employer takeaway

Someone who will not hand you a merger model whose accretion is an artefact of the
financing structure and call it a recommendation — and who will tell you, unprompted, the
annual synergy the price requires versus the synergy anyone has actually identified.

---

## Current state

Sourced and in the repo: consideration terms, CVR structure and all three milestones,
stated EV, tender-derived share count, disclosed EPS guidance, integration structure.

Sourced across three passes: target revenue, operating income, net income, effective
tax rate, net debt, and book equity from Abiomed's own FY2022 10-K and 30 June 2022
10-Q (the correct pre-announcement balance sheet date — see Key findings); J&J's own
headline goodwill, amortizable intangibles, IPR&D, pretax acquisition costs, and the
Abiomed-specific deferred tax liability from J&J's 10-Ks. Total liabilities assumed is a
*demonstrated* estimate (~$1,957mm), not a single disclosed line — the DTL plus
Abiomed's own last-known operating liabilities, summed and tagged as a computation
rather than a citation. The CVR's probability weight (0.495) is likewise a cited,
circumstantial *estimate*, not a confirmed fair value — see its own citation for why.

Outstanding — `python scripts/check_inputs.py` prints each with the filing that contains
it:

| Input | Source |
|---|---|
| CVR acquisition-date fair value (booked) | J&J FY2022 10-K, business combination footnote — distinct from both the $1.6bn undiscounted maximum and the 0.495 circumstantial weight already in use |
| Financing mix | J&J FY2022 10-K, cash flow financing section and debt footnote |
| Buyer standalone forward | Trellis run on CIK 200406 (pipeline run, not research) |

One figure still rests on a secondary source and is flagged as such in the code: the
$252 unaffected share price. Needs confirming against a primary exchange/market-data
record before any premium derived from it is quoted.

## Running it

```bash
pip install -e .
pip install -e ".[dev]"

python scripts/project_status.py    # is anything still unbuilt or uncollected?
python scripts/check_inputs.py      # collection status for the real deal
python scripts/run_trellis_jnj.py   # buyer forecast (needs TRELLIS_USER_AGENT + network)
python scripts/run_jnj_abiomed.py   # THE REAL MODEL, across all financing scenarios
python scripts/demo_mechanics.py    # end-to-end run on the synthetic fixture
python -m pytest -q                 # 173 tests
```

`demo_mechanics.py` runs on invented numbers and says so on every screen. It exists to
exercise the pipeline and show the output shape, not to say anything about any real deal.

## Known limitations

Stated rather than discovered:

- **No bargain purchase, NCI, measurement-period adjustments, or replacement share-based
  awards.** Each is real ASC 805 territory and each is out of scope.
- **No CVR remeasurement.** Post-close mark-to-market of the CVR liability runs through
  reported earnings in later years. Modelled at acquisition date only.
- **Calendarization is linear within the year.** Better than ignoring a fiscal offset,
  worse than rebuilding from the target's quarterly filings — which is the upgrade path.
- **Synergies are discounted at the buyer's WACC.** That is the convention and it is
  arguably too generous: synergy cash flows are riskier than the buyer's existing
  business. The rate is an explicit input, not inherited silently.
- **Exit multiple defaults to entry.** The conservative convention, and still an
  assumption; the model flags it either way.

## Licence

MIT.
