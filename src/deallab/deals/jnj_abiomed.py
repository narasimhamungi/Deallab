"""
Johnson & Johnson / Abiomed, announced 1 November 2022, closed 22 December 2022.

This file is the deal's evidence base. Every figure is either quoted from a named
source or explicitly marked as not yet collected -- there are no placeholder numbers
anywhere in it. A merger model whose inputs are plausible-but-invented produces an
answer indistinguishable from a researched one, and this deal was chosen precisely
because it has a public answer key to check against.

**Why this deal.** ValuationLab established that J&J cannot be valued as one company:
pharma peer dispersion widens with more peers (2.5x to 4.7x), which is structural
patent-cliff timing rather than sample noise, while the MedTech segment values cleanly
on its own peer group at roughly $101-157bn EV. Abiomed is a real acquisition into
exactly that segment. So the target valuation DealLab consumes is one ValuationLab would
stand behind, not a company-wide blend it already flagged as unreliable.

**The answer key.** J&J guided the transaction as slightly dilutive to neutral to
adjusted EPS in the first year including financing impact, accretive by roughly $0.05 in
2024, and increasingly accretive thereafter. The model's job is to land near that and to
explain any gap -- not merely to produce output.

**Two structural features this deal has and a template cannot handle.** First, the CVR:
up to $35.00 per share on three separate milestones, 9.2% of the headline price, which
must be recognised at acquisition-date fair value under ASC 805. Second, the disclosed
decision to run Abiomed as a standalone business within J&J MedTech -- an explicit
choice to forgo integration cost synergies. Assuming a generic percentage-of-opex cost
synergy for this deal contradicts a disclosed fact.

**A correction made against this file's own earlier guidance.** An prior version of this
module directed the target-balance-sheet pull to Abiomed's 10-Q for the quarter ended
30 September 2022, calling it "the last balance sheet before announcement." That is
wrong: the Nov 1 2022 announcement predates that filing -- it was filed 3 November 2022,
two days AFTER announcement, as part of Abiomed's ordinary quarterly cycle. The actual
last balance sheet public at signing is the 10-Q for the quarter ended 30 June 2022,
filed 4 August 2022. Figures below now use that date. Left here rather than silently
fixed, because the same mistake (reaching for the nearest-dated filing without checking
it was actually public before the trigger event) is a realistic failure mode, not a typo.

**An unresolved finding, not silently squared away.** Using the figures this file
actually carries -- $380.00 x 45.091184mm shares = $17,134.65mm upfront, less
$1,004.197mm of net cash (30 June 2022, corroborated word-for-word by Abiomed's own 4
August 2022 press release) -- gives an upfront-only derived EV of $16,130.45mm against
J&J's stated "~$16.6 billion": a $469.5mm (2.8%) shortfall. Two readings, neither
confirmed:
(a) J&J's figure describes the $380 cash consideration only (the CVR is mentioned
separately in the same sentence as an addition, not folded into "$16.6 billion") and is
simply a rounded, approximate PR number rather than a rigorously netted EV -- the more
natural reading of the sentence, and the one this file defaults to.
(b) The stated EV already reflects the CVR at a high probability weight: at ~30% of the
$35.00 maximum (45.091184mm x $35.00 x 0.30 = $473.5mm) the gap closes almost exactly --
which would be a striking coincidence, or would mean J&J's deal team assumed materially
higher CVR realisation than this file's own placeholder weight. Not adopted, because
nothing in the announcement or close 8-Ks supports reading "$16.6 billion... which
includes cash acquired" as CVR-inclusive; noted here so a future pass with the actual
CVR fair value (see `MISSING`) can test it directly instead of guessing.
`terms.ev_reconciliation` surfaces the upfront-only gap on every run rather than hiding
it inside a chosen convention.

**A later pass gives (b) more credibility than it had, and a subsequent pass tightened**
**the estimate further -- in the direction that makes (b) slightly weaker, not stronger,**
**and that is reported plainly rather than smoothed over.** `CVR.probability_weight` is
now an independently derived estimate (0.541, primarily from J&J's own FY2024 10-K
explicitly attributing a $17.7bn acquisition total to Abiomed by name -- see
JNJ_10K_FY2024_ACQUISITION_TOTAL -- corroborated by an earlier, less direct 0.495
estimate from J&J's aggregate contingent-consideration rollforward). Running the FULL
reconciliation with the current weight -- upfront + CVR at fair value ($854mm) + net
debt -- gives a derived EV of $16,984mm against the stated $16,600mm: a +2.3% gap, just
OUTSIDE this file's 2% "ties" threshold (an earlier pass, using the less-triangulated
0.495 weight, had this at +1.9%, just inside it). The CVR-inclusive number still lands
closer to the stated EV than the upfront-only gap (-2.8%) does, on the OPPOSITE side --
so the broad shape of the earlier finding (the stated EV is not purely upfront-cash-only)
survives -- but improving the evidence made the precise "ties" call flip, which is worth
knowing plainly: the underlying uncertainty here has not been resolved to the point that
a threshold this tight means anything on its own. Both reconciliations are left visible
in `check_inputs.py` rather than reporting only the one that ties.

STATUS: deal terms, guidance, target FY2022 fundamentals, and J&J's own headline PPA
figures (goodwill, amortizable intangibles, IPR&D, acquisition costs, and now the
Abiomed-specific deferred tax liability) are sourced. The CVR probability weight is now
an ASSUMED, cited estimate (0.495, from circumstantial evidence) rather than a blocking
unset value. Two items remain genuinely outstanding -- the CVR's precise booked fair
value and J&J's actual financing mix -- plus one mechanical item, the buyer-side Trellis
forecast, which is a pipeline run rather than a research task. See `MISSING` below.
"""

from __future__ import annotations

from ..provenance import Input, assumed, demonstrated, sourced, unsourced
from ..terms import Consideration, ContingentValueRight, DealTerms

# --- Citations ----------------------------------------------------------------------

ANNOUNCE_8K = ("J&J Form 8-K / SC TO-C exhibit 99.1, 1 November 2022 "
               "(sec.gov/Archives/edgar/data/200406/000119312522274491/d395813dex991.htm)")
CLOSE_8K = ("J&J Form 8-K exhibit 99.1, 22 December 2022 "
            "(sec.gov/Archives/edgar/data/200406/000119312522311072/d428734dex991.htm)")
ABIOMED_10Q_JUN2022 = ("Abiomed 10-Q, quarter ended 30 June 2022, filed 4 August 2022 "
                       "(sec.gov/Archives/edgar/data/815094/000095017022014795/"
                       "abmd-20220630.htm)")
ABIOMED_PR_AUG2022 = ("Abiomed press release, 4 August 2022 (Q1 FY2023 results) "
                      "(businesswire.com/news/home/20220804005397/en)")
ABIOMED_10K_FY2022 = ("Abiomed 10-K, fiscal year ended 31 March 2022, filed 20 May 2022 "
                      "(sec.gov/Archives/edgar/data/815094/000095017022010402/"
                      "abmd-20220331.htm)")
JNJ_10Q_Q1_2023 = ("J&J 10-Q, quarter ended 2 April 2023, filed 28 April 2023 "
                   "(investor.jnj.com/files/doc_financials/2023/q1/10Q-Final.pdf)")
JNJ_10K_FY2024 = ("J&J 10-K, fiscal year ended 29 December 2024 -- retrospective "
                  "business-acquisitions footnote covering the finalised (fiscal 2023) "
                  "Abiomed purchase price allocation "
                  "(sec.gov/Archives/edgar/data/200406/000020040625000038/"
                  "jnj-20241229.htm)")
JNJ_10K_FY2024_OTHER_EXPENSE_NOTE = (
    "J&J 10-K FY2024, MD&A 'Other (Income) Expense, Net' table and footnotes "
    "(sec.gov/Archives/edgar/data/200406/000020040625000038/jnj-20241229.htm): Total "
    "Other (Income) Expense, Net was $4.7bn expense (FY2024), $6.6bn expense (FY2023), "
    "$(1.9)bn -- i.e. $1.9bn of INCOME -- (FY2022). Footnotes attribute this to: (1) "
    "'charges primarily for talc matters' in FY2024 and FY2023 (Note 19), partly offset "
    "in FY2023 by ~$0.3bn of favorable IP litigation settlements; (2) FY2024 'primarily "
    "related to the acquisition of Shockwave', FY2023 'primarily related to the "
    "impairment of Ponvory and one-time integration costs related to the acquisition of "
    "Abiomed'; (3) FY2024 includes a $0.4bn loss 'on the completion of the debt for "
    "equity exchange of the retained stake in Kenvue.'")
JNJ_ADJUSTED_TAX_RATE_DISCLOSURES = (
    "J&J's own disclosed ADJUSTED (non-GAAP) effective tax rate, from quarterly "
    "earnings-release exhibits (sec.gov/Archives/edgar/data/200406/...): Q1 2021 "
    "16.5%; Q1 2024 16.3%; Q1 2025 16.3%. Tight range despite GAAP effective tax rate "
    "swinging far wider across the same years (per this file's own Trellis-derived "
    "history: roughly 8%-17% year to year) -- consistent with J&J's own stated purpose "
    "for the adjusted figure, which explicitly excludes 'the effects of an acquisition, "
    "restructuring, litigation, and changes in applicable laws and regulations.' Only "
    "three quarterly data points located this pass, not a complete disclosed annual "
    "series -- reading a single go-forward rate off three Q1 prints is itself a choice, "
    "not a citation, which is why this stays tagged ASSUMED rather than SOURCED.")
JNJ_10K_FY2024_ACQUISITION_TOTAL = (
    "'During the fiscal year 2022, certain businesses were acquired for $17.7 billion, "
    "net of cash acquired. The fiscal year 2022 acquisitions primarily included "
    "Abiomed, Inc. (Abiomed). The remaining acquisitions were not material.' J&J 10-K, "
    "fiscal year ended 29 December 2024 "
    "(sec.gov/Archives/edgar/data/200406/000020040625000038/jnj-20241229.htm). Unlike "
    "the $792mm contingent-consideration 'Additions' line used for the CVR weight "
    "below, this figure is EXPLICITLY attributed to Abiomed by name (with other 2022 "
    "activity called out as immaterial) -- a more direct disclosure, used to triangulate "
    "the CVR fair value a second, independent way. Derivation: this file's own upfront "
    "consideration ($17,135mm) less cash acquired ($300mm, ACTUAL_PPA) = $16,835mm "
    "upfront net of cash. $17,700mm (disclosed) - $16,835mm = $865mm implied CVR fair "
    "value -- against a $1,600mm undiscounted maximum, an implied weight of 0.541. "
    "This is the primary basis for CVR.probability_weight below; the older $792mm/0.495 "
    "estimate is retained as corroborating (not primary) evidence, since it drew on "
    "J&J's AGGREGATE contingent-consideration balance across all acquisitions, not one "
    "attributed to Abiomed specifically.")
JNJ_CONTINUING_OPERATIONS_RESTATEMENT = (
    "RESOLVES an open question this file previously carried unanswered: does Trellis's "
    "historical revenue for J&J reflect the ORIGINALLY-FILED consolidated total "
    "(including Consumer Health) or an already-restated, continuing-operations-only "
    "figure? Confirmed, with two primary sources, that it is the LATTER -- which is "
    "the right basis for this model, not a data quality problem to work around.\n\n"
    "(1) J&J's ORIGINAL, as-filed FY2022 worldwide sales, from the 4Q2022 earnings "
    "release exhibit (sec.gov/Archives/edgar/data/200406/000020040623000005/"
    "a2022q4exhibit992.htm): $94,943mm, all three segments (Consumer Health $14,953mm "
    "+ Pharmaceutical $52,563mm + MedTech $27,427mm = $94,943mm exactly).\n\n"
    "(2) J&J's FY2023 10-K, Note 17 (sec.gov/Archives/edgar/data/200406/"
    "000020040624000013/jnj-20231231.htm), states plainly: 'Following the separation "
    "of the Consumer Health business in the fiscal third quarter of 2023, the Company "
    "is now organized into two business segments: Innovative Medicine ... and MedTech. "
    "The segment results have been recast for ALL PERIODS to reflect the continuing "
    "operations of the Company.'\n\n"
    "Mechanism: SEC EDGAR's XBRL company-facts API returns the most recently tagged "
    "value for a given concept and period across ALL filings that report it. Once J&J's "
    "post-separation filings retagged FY2021/FY2022 as continuing-operations-only "
    "(Innovative Medicine + MedTech, ex-Kenvue), that became the value Trellis's ingest "
    "picks up for those historical periods -- not the larger, originally-filed "
    "consolidated total above. This is precisely the two-segment, ex-Consumer-Health "
    "entity relevant to the Abiomed deal (Abiomed sits in MedTech), so the buyer "
    "forecast's historical base is already on the correct footing without any "
    "adjustment this file needs to make. Abiomed's own 9-day, immaterial FY2022 stub "
    "(see BUYER_FORECAST_BASE_YEAR_RATIONALE) means the FY2022 base is effectively "
    "J&J-continuing-operations, pre-Abiomed -- the exact counterfactual this model "
    "needs, arrived at without deliberate engineering.")

# --- Consideration ------------------------------------------------------------------

CASH_PER_SHARE = sourced(
    "cash_per_share", 380.00,
    f"Upfront payment of $380.00 per share in cash, all outstanding shares, via tender "
    f"offer. {ANNOUNCE_8K}")

CVR = ContingentValueRight(
    max_per_share=sourced(
        "cvr_max_per_share", 35.00,
        f"Non-tradeable CVR entitling the holder to up to $35.00 per share in cash on "
        f"clinical and commercial milestones. {ANNOUNCE_8K}"),
    probability_weight=assumed(
        "cvr_probability_weight", 0.541,
        "0.541 = $865mm implied CVR fair value / $1,600mm undiscounted maximum. "
        "PRIMARY basis, per JNJ_10K_FY2024_ACQUISITION_TOTAL: J&J's own FY2024 10-K "
        "attributes a $17.7bn 'net of cash acquired' total explicitly to Abiomed (2022's "
        "only material acquisition); netting this file's own upfront-less-cash figure "
        "($17,135mm - $300mm = $16,835mm) against it implies an $865mm CVR fair value. "
        "CORROBORATING (secondary) basis, per the earlier pass: 0.495 = $792mm/$1,600mm, "
        "from the 'Additions' line in J&J's AGGREGATE contingent-consideration "
        "rollforward across ALL acquisitions (sec.gov/Archives/edgar/data/200406/"
        "000020040624000013/jnj-20231231.htm) -- Beginning Balance $533mm (FY2021) -> "
        "Additions $792mm (FY2022) -> Ending Balance $1,120mm, not Abiomed-specific by "
        "name, attributed only by timing and magnitude.\n\n"
        "Both independent triangulations land within 5 points of each other (54.1% vs "
        "49.5%) despite drawing on different disclosures -- convergent, not identical, "
        "evidence. The newer estimate is used as the point figure because its source "
        "sentence names Abiomed directly and calls the year's other acquisitions "
        "immaterial, which the older aggregate-rollforward evidence cannot claim. "
        "STILL CIRCUMSTANTIAL, NOT CONFIRMED: neither disclosure states 'the CVR "
        "liability was recognised at $X' in so many words: both are this file's own "
        "arithmetic run backward from a broader disclosed total. J&J's own acquisition-"
        "date fair value for the CVR liability specifically, stated at that grain, "
        "remains the SOURCED figure to find and would supersede this -- see "
        "`cvr_acquisition_date_fair_value` in MISSING."),
    milestones=(
        "Three independent milestones, per the merger agreement: (1) $17.50/share if "
        "Abiomed product net sales exceed $3.7bn during J&J's fiscal Q2 2027 through "
        "fiscal Q1 2028, or $8.75/share if that threshold is instead met in any rolling "
        "four-quarter period up to the end of fiscal Q1 2029; (2) $7.50/share on FDA "
        "premarket approval of Impella in STEMI patients without cardiogenic shock by "
        "1 January 2028; (3) $10.00/share on first publication of a Class I "
        "recommendation for Impella in high-risk PCI. Because the milestones are "
        "independent and partly time-conditional, a single scalar probability weight is "
        "a simplification -- the defensible version prices each milestone separately."),
    tradeable=False,
)

# Two independent figures for this, kept both visible rather than silently picking one:
#
# (1) Derived from the tender result: 25,759,195 shares tendered, stated as ~57.1% of
#     then-outstanding -> 25,759,195 / 0.571 = 45.11mm. Inherits rounding on "~57.1%".
# (2) Directly stated in the Abiomed 10-Q cover page: "As of October 28, 2022,
#     45,091,184 shares... were outstanding" -- filed 3 Nov 2022, i.e. the actual count
#     four days after announcement, essentially contemporaneous with signing.
#
# The two agree to within 0.05% (45.11mm vs 45.091mm), which is a genuine cross-check
# that the tender-based derivation was sound. (2) is used as the primary figure since
# it is a direct disclosure, not an inference from a rounded percentage -- but note it
# is still BASIC outstanding, not fully diluted; in-the-money options and RSUs also
# received consideration and are not captured here.
TARGET_SHARES_OUTSTANDING = sourced(
    "target_shares_outstanding_mm", 45.091184,
    "'As of October 28, 2022, 45,091,184 shares of the registrant's common stock... "
    "were outstanding.' Abiomed 10-Q cover page, quarter ended 30 September 2022, "
    "filed 3 November 2022 (sec.gov/Archives/edgar/data/815094/000095017022021880/"
    "abmd-20220930.htm). Cross-checked against the independently tender-derived "
    "25,759,195 / 0.571 = 45.11mm (a 0.05% agreement). BASIC outstanding, not fully "
    "diluted.")

STATED_EV = sourced(
    "stated_enterprise_value_mm", 16_600.0,
    f"'Enterprise value of approximately $16.6 billion which includes cash acquired'. "
    f"{ANNOUNCE_8K}. Note the phrasing: 'EV including cash acquired' is not standard "
    f"enterprise-value language and this figure should not be assumed to be "
    f"equity value plus net debt on the conventional definition.")

TARGET_SHARE_PRICE_UNAFFECTED = sourced(
    "target_share_price_unaffected", 252.00,
    "Abiomed close of ~$252 on 31 October 2022, the last trading day before "
    "announcement, per contemporaneous trade coverage (GeneOnline, 1 Nov 2022). "
    "SECONDARY SOURCE -- verify against an exchange or market-data record before "
    "quoting the implied premium; a premium calculation resting on a blog's price is "
    "the weakest link in an otherwise filing-sourced chain.")

TARGET_NET_DEBT = sourced(
    "target_net_debt_mm", -1_004.197,
    f"Cash $180.492mm + short-term marketable securities $663.829mm + long-term "
    f"marketable securities $159.876mm = $1,004.197mm; no debt on the balance sheet at "
    f"all (no debt line item exists). {ABIOMED_10Q_JUN2022}. Corroborated directly by "
    f"Abiomed's own words: '$1.004 billion of cash, cash equivalents and marketable "
    f"securities and no debt' as of this date. {ABIOMED_PR_AUG2022}. Negative = net "
    f"cash, per this file's sign convention. See the module docstring: this does NOT "
    f"cleanly reconcile to J&J's stated EV, and that gap is left open rather than "
    f"resolved by picking a different date or convention.")

TARGET_BOOK_EQUITY = sourced(
    "target_book_equity_mm", 1_536.196,
    f"Total stockholders' equity, 30 June 2022. {ABIOMED_10Q_JUN2022}.")

TERMS = DealTerms(
    acquirer="Johnson & Johnson",
    target="Abiomed, Inc.",
    announced="2022-11-01",
    closed="2022-12-22",
    consideration_type=Consideration.ALL_CASH,
    cash_per_share=CASH_PER_SHARE,
    target_shares_outstanding=TARGET_SHARES_OUTSTANDING,
    target_net_debt=TARGET_NET_DEBT,
    stated_enterprise_value=STATED_EV,
    cvr=CVR,
    target_share_price_unaffected=TARGET_SHARE_PRICE_UNAFFECTED,
    source=f"{ANNOUNCE_8K}; {CLOSE_8K}",
)

# --- Disclosed guidance: the answer key ---------------------------------------------

GUIDANCE = {
    "year_one_adjusted_eps": (
        "Slightly dilutive to neutral to adjusted earnings per share in the first year, "
        f"considering the impact of financing. {CLOSE_8K}"),
    "2024_adjusted_eps": (
        f"Accretive by approximately $0.05 in 2024, and increasingly accretive "
        f"thereafter. {CLOSE_8K}"),
    "year_of_close": (
        f"'The transaction will not have a material impact on financial results for "
        f"2022.' {CLOSE_8K} -- consistent with a 22 December close leaving a nine-day "
        f"stub in J&J's fiscal 2022."),
    "revenue_growth": (
        f"'The transaction will accelerate pro forma MedTech and Johnson & Johnson "
        f"enterprise revenue growth.' {CLOSE_8K}"),
    "integration": (
        f"Abiomed operates as a standalone business within J&J MedTech. {CLOSE_8K}. "
        f"Material cost synergies should NOT be assumed against a disclosed standalone "
        f"operating model."),
}

GUIDANCE_YEAR_ONE_BOUNDS = (-0.01, 0.005)  # "slightly dilutive to neutral", as a fraction
GUIDANCE_2024_ACCRETION_USD = 0.05

# --- Target fundamentals: sourced from the FY2022 10-K (year ended 31 March 2022) ---
# All four below are from the SAME filing and tie to each other exactly:
# 190.560 (pretax) - 54.055 (tax) = 136.505 (net income) -- an internal consistency
# check the earlier secondary-sourced $1,032mm revenue figure could not offer.

TARGET_REVENUE_FY2022 = sourced(
    "target_revenue_fy2022_mm", 1_031.753,
    f"Total revenue, fiscal year ended 31 March 2022: $1,031,753 thousand, +21.7% "
    f"year on year. {ABIOMED_10K_FY2022}. Supersedes an earlier $1,032.0mm figure taken "
    f"from secondary trade coverage -- the two agree to within $0.25mm, which is itself "
    f"a useful confirmation the secondary source was reliable, but this is now the "
    f"primary citation. Note the fiscal year end: this is April 2021 - March 2022, NOT "
    f"calendar 2022, and must be calendarized onto J&J's December year end (see "
    f"calendarize.py) before any pro-forma combination.")

TARGET_OPERATING_INCOME_FY2022 = sourced(
    "target_operating_income_fy2022_mm", 140.720,
    f"Income from operations, fiscal year ended 31 March 2022: $140,720 thousand "
    f"(revenue $1,031,753k less cost of revenue $188,158k, R&D $163,403k, SG&A "
    f"$423,486k, and a one-time $115,986k acquired-IPR&D charge). {ABIOMED_10K_FY2022}.")

TARGET_NET_INCOME_FY2022 = sourced(
    "target_net_income_fy2022_mm", 136.505,
    f"Net income, fiscal year ended 31 March 2022: $136,505 thousand. Ties exactly to "
    f"income before taxes ($190,560k) less the total income tax provision ($54,055k). "
    f"{ABIOMED_10K_FY2022}.")

TARGET_EFFECTIVE_TAX_RATE_FY2022 = sourced(
    "target_effective_tax_rate_fy2022", 54.055 / 190.560,
    f"$54,055k tax / $190,560k pretax income = 28.4%, well above the 21% federal "
    f"statutory rate. {ABIOMED_10K_FY2022}. Driven by a $70,066k FOREIGN pretax LOSS "
    f"sitting alongside a $260,626k US pretax GAIN in the geographic split -- foreign "
    f"losses generating no current tax benefit (valuation-allowance territory) push the "
    f"blended rate up even though consolidated pretax income is positive. Confirms the "
    f"earlier note that this rate should be read from the footnote, not inferred by "
    f"dividing a single blended tax line by pretax income at face value.")

# --- J&J's own purchase price allocation, sourced from its own filings -------------
# J&J's FY2024 10-K carries the FINALISED (post fiscal-2023 measurement-period
# adjustment) allocation, retrospectively, since Abiomed remains material. This is a
# better source than the original FY2022 10-K for the final numbers -- initial PPAs are
# provisional under ASC 805 and get trued up over the following year, which is exactly
# what happened here (see PPA_MEASUREMENT_PERIOD_ADJUSTMENT below).
#
# Two of these are direct model INPUTS (ready to build an IntangibleClass with);
# the rest are ANSWER-KEY figures -- J&J's own computed goodwill and total identifiable
# assets, to check the model's *derived* allocation against once every input is in,
# the same role GUIDANCE plays for accretion.

INTANGIBLE_AMORTIZABLE_FV = sourced(
    "intangible_amortizable_fv_mm", 6_600.0,
    f"'Amortizable intangible assets for $6.6 billion.' {JNJ_10K_FY2024}. Per "
    f"{JNJ_10Q_Q1_2023}: 'primarily comprised of already in-market products of the "
    f"Impella platform with an average weighted life of 14 years' -- a single bucket, "
    f"not split by developed-technology/customer-relationship sub-category as this "
    f"file originally guessed the disclosure would be. Ready to use directly as an "
    f"`IntangibleClass` input: fair_value=6,600, useful_life_years=14.")

IPRD_FV = sourced(
    "iprd_fv_mm", 1_100.0,
    f"'IPR&D for $1.1 billion.' {JNJ_10K_FY2024}. Per {JNJ_10Q_Q1_2023}: indefinite-"
    f"lived, 'valued for technology programs for unapproved products' using "
    f"'probability-adjusted cash flow projections discounted for the risk inherent in "
    f"such projects,' with a probability-of-success factor ranging 52%-70%. NOT "
    f"amortised (indefinite-lived, tested for impairment like goodwill) -- this file's "
    f"`IntangibleClass` always amortises over a stated useful life and has no "
    f"indefinite-lived case. A model run using this figure must either exclude it from "
    f"`intangibles` (folding it into goodwill, understating goodwill's true share) or "
    f"treat it as a finite-life class with a placeholder life, flagged clearly as a "
    f"simplification either way -- stated here rather than discovered at run time.")

MARKETABLE_SECURITIES_ACQUIRED = sourced(
    "marketable_securities_acquired_mm", 600.0,
    f"'Marketable securities of $0.6 billion' within total assets acquired. "
    f"{JNJ_10K_FY2024}. Notably smaller than the $1,004.2mm Abiomed itself reported "
    f"holding at 30 June 2022 (TARGET_NET_DEBT above) -- a further, separate gap this "
    f"file does not attempt to close (different measurement dates and classification "
    f"bases; not investigated further this pass).")

DEFERRED_TAX_LIABILITY_ABIOMED = sourced(
    "deferred_tax_liability_abiomed_mm", 1_800.0,
    "'Amount is inclusive of the $1.8 billion deferred tax liability due to the "
    "acquisition of Abiomed.' J&J 10-K, fiscal year ended 1 January 2023, footnote to "
    "the deferred tax asset/liability table (sec.gov/Archives/edgar/data/200406/"
    "000020040623000016/jnj-20230101.htm). Direct and unambiguous -- explicitly "
    "attributed to this acquisition by name, unlike the CVR addition estimate below.")

TOTAL_LIABILITIES_ASSUMED_ESTIMATE = demonstrated(
    "total_liabilities_assumed_estimate_mm", 156.757 + 1_800.0,
    "Abiomed's own total liabilities of $156.757mm (30 September 2022 10-Q -- the "
    "most recent pre-acquisition figure this file has sourced; Abiomed's actual "
    "12/22/2022 acquisition-date balance sheet would differ somewhat and was not "
    "pulled) PLUS the $1.8bn step-up deferred tax liability above, which is additional "
    "to and distinct from Abiomed's own pre-existing $0.689mm DTL already inside that "
    "$156.757mm. This is NOT a single disclosed line from J&J's own PPA table -- it is "
    "this file's sum of two independently sourced figures, presented as a reasoned "
    "estimate (~$1,956.8mm) rather than a primary citation for the total. Cross-checks "
    "reasonably against the earlier top-down estimate implied by the accounting "
    "identity in ACTUAL_PPA_SOURCE (~$2.2bn using the circumstantial CVR estimate "
    "below) -- the two independent approaches land within ~$250mm of each other.")

ADVISORY_FEES_PRETAX = sourced(
    "advisory_fees_pretax_mm", 300.0,
    f"'In 2022, the Company recorded acquisition related costs before tax of "
    f"approximately $0.3 billion, which was recorded in Other (income)/expense.' "
    f"{JNJ_10Q_Q1_2023}. Expensed as incurred, not capitalised into goodwill -- "
    f"consistent with this file's `financing.py` treatment. Ready to use directly as "
    f"`FinancingPlan.advisory_fees`.")

UPFRONT_NET_OF_CASH_ACQUIRED = sourced(
    "upfront_net_of_cash_acquired_mm", 17_100.0,
    f"'An upfront payment of $380.00 per share in cash, amounting to $17.1 billion, "
    f"net of cash acquired.' {JNJ_10K_FY2024}. A DIFFERENT figure from this file's own "
    f"derived gross upfront consideration (TERMS.upfront_equity_purchase_price() = "
    f"$17,134.65mm at the sourced share count) -- the two are close (~$35mm apart) "
    f"only by coincidence of rounding, since J&J's figure is explicitly net of cash "
    f"acquired (narrowly: cash and equivalents, ~$0.3bn per the figure below) while "
    f"this file's derived figure is gross. Not reconciled into TERMS -- kept as a "
    f"separate cross-check figure, same discipline as the EV gap below.")

# --- Answer-key figures: J&J's own computed results, to check the model against -----

ACTUAL_PPA = {
    "goodwill_mm": 11_100.0,
    "amortizable_intangibles_mm": INTANGIBLE_AMORTIZABLE_FV.value,
    "iprd_mm": IPRD_FV.value,
    "marketable_securities_acquired_mm": MARKETABLE_SECURITIES_ACQUIRED.value,
    "total_assets_acquired_net_of_cash_mm": 20_100.0,
    "cash_acquired_mm": 300.0,
    "cvr_aggregate_undiscounted_max_mm": 1_600.0,  # NOT the booked acquisition-date FV
}
ACTUAL_PPA_SOURCE = (
    f"'The fair value of the acquisition was allocated to assets acquired of $20.1 "
    f"billion (net of $0.3 billion cash acquired), primarily to goodwill for $11.1 "
    f"billion, amortizable intangible assets for $6.6 billion, IPR&D for $1.1 billion, "
    f"marketable securities of $0.6 billion and liabilities [assumed of an amount not "
    f"captured in this search pass].' {JNJ_10K_FY2024}. The four itemised categories "
    f"sum to $19.4bn against a stated $20.1bn total -- the ~$0.7bn difference is other "
    f"identifiable assets (receivables, inventory, PP&E) not broken out in this summary "
    f"disclosure. Liabilities assumed and the CVR's specific acquisition-date fair "
    f"value (distinct from the $1.6bn undiscounted maximum above) were NOT located this "
    f"pass -- both remain in MISSING.")

PPA_MEASUREMENT_PERIOD_ADJUSTMENT = (
    f"Two different figures for the same fiscal-2023 true-up appear across J&J's own "
    f"filings: {JNJ_10Q_Q1_2023} states adjustments 'netting to approximately $0.1 "
    f"billion with an offsetting increase to goodwill'; {JNJ_10K_FY2024} states "
    f"'approximately $0.2 billion.' Not an error to resolve -- ASC 805 measurement-"
    f"period adjustments accrue over the year following acquisition, so a Q1 snapshot "
    f"and a fully-elapsed final figure are expected to differ. The $11.1bn goodwill "
    f"figure above is the later, more complete one.")

EV_RESTATEMENT_NOTE = (
    f"J&J's own headline EV figure drifted across filings: 'approximately $16.6 "
    f"billion' at announcement/close ({ANNOUNCE_8K}; {CLOSE_8K}) versus 'approximately "
    f"$16.5 billion' in the FY2024 10-K's retrospective description. A $0.1bn move in a "
    f"company's own restatement of its own headline number is further, independent "
    f"evidence for this file's existing reading of that figure as an approximate, "
    f"rounded PR number rather than one meant to reconcile to the cent -- see the "
    f"module docstring's EV-gap discussion.")

# --- Buyer-side (J&J standalone) forecast driver decisions --------------------------
#
# Running J&J's own history through Trellis (scripts/run_trellis_jnj.py) surfaced real
# volatility that needed explaining before the resulting forecast could be trusted:
# GAAP net margin swung 17.8% (2021) -> 26.5% (2022) -> 22.4% (2023) -> 15.8% (2024,
# the LOW point despite +11% revenue growth that year) -> 28.5% (2025). J&J's own FY2024
# 10-K explains why (JNJ_10K_FY2024_OTHER_EXPENSE_NOTE): talc litigation charges swinging
# from $1.9bn of income (2022) to $6.6bn of expense (2023) to $4.7bn of expense (2024),
# plus a $0.4bn loss on completing the Kenvue debt-for-equity exchange in 2024 -- which
# is also the most likely explanation for the $25.2bn FY2024 retained-earnings-rollforward
# gap Trellis's own structural check flagged (a debt-for-equity exchange typically moves
# value through additional paid-in capital, not net income; Trellis's RE check has no
# line for that transaction type, which is a real limitation of the check, not a bug).
#
# Two decisions follow from this, both judgment calls, both cited and flagged ASSUMED
# rather than silently taken from whatever derive_drivers_from_history(table, base_year)
# would produce with its defaults.

BUYER_TAX_RATE_OVERRIDE = assumed(
    "buyer_tax_rate_override", 0.16,
    f"J&J's own GAAP effective tax rate, as Trellis derives it from net income, is "
    f"driven far more by the items above than by underlying tax position -- the same "
    f"volatility that distorts net margin distorts a net-income-denominator tax rate "
    f"identically. J&J's own disclosed ADJUSTED effective tax rate is far more stable "
    f"(15-17% across every quarter located): {JNJ_ADJUSTED_TAX_RATE_DISCLOSURES}. 0.16 "
    f"is the midpoint of that range, not a single disclosed annual figure -- ASSUMED, "
    f"not SOURCED, and correctly so. Applied via `dataclasses.replace()` on Trellis's "
    f"own derived Drivers AFTER derivation, not through Trellis's `overrides` "
    f"parameter: that mechanism only accepts interest_rate, debt_repayment, and "
    f"revolver_limit (checked directly against trellis/forecast.py) -- it does not "
    f"support overriding an income-statement ratio driver like tax_rate at all. A real "
    f"limitation of Trellis's current override mechanism, worth a note upstream, not "
    f"something to route around silently here.")

BUYER_DILUTED_SHARES = sourced(
    "buyer_diluted_shares_mm", 2_667.5,
    "J&J average shares outstanding -- diluted, 2,667.5mm for the nine months ended "
    "2 October 2022. J&J 10-Q Q3 2022, EPS reconciliation note "
    "(s203.q4cdn.com/636242992/files/doc_financials/2022/q3/"
    "Johnson-Johnson-3Q2022-Form-10-Q.pdf). This is the last diluted share count J&J "
    "disclosed BEFORE the 1 November 2022 announcement -- the same "
    "last-public-figure-before-the-trigger-event discipline applied to Abiomed's own "
    "share count and balance sheet (see the docstring note about the 30 Sept 2022 10-Q "
    "trap). Not in Trellis's schema, which covers statement line items, not per-share "
    "data -- so this is sourced by hand rather than pipeline-derived. Note it is the "
    "nine-month average, not a full-year figure; J&J's full-year 2022 diluted average "
    "was marginally different (~2,664mm per third-party aggregators, not used here "
    "since it post-dates announcement and is not a primary citation).")

FINANCING_MIX_NOT_DISCLOSED = (
    "J&J never disclosed how it funded the Abiomed purchase. Searched the announcement "
    "and close 8-Ks, the completion press release, and trade coverage: every one "
    "describes the consideration ($380.00/share cash plus CVR) and none describes the "
    "source of funds. No commercial-paper or note issuance was found tied to this "
    "transaction by name. This is a genuine disclosure gap, not a research failure to "
    "be papered over with a plausible split.\n\n"
    "The response is a SENSITIVITY, not a guess. J&J's own guidance said year-one "
    "adjusted EPS would be 'slightly dilutive to neutral... considering the impact of "
    "financing' -- so the mix is load-bearing for the single number this model is "
    "graded against, and picking one split would quietly determine the answer. "
    "FINANCING_SCENARIOS below spans the plausible range instead; "
    "scripts/run_jnj_abiomed.py runs all of them and reports the spread. If the "
    "conclusion holds across every scenario, the undisclosed mix does not matter. If it "
    "flips somewhere in the range, THAT is the finding -- and it is a more honest "
    "output than a single figure resting on an invented funding assumption.")

BUYER_DRIVER_LOOKBACK_YEARS = 5

BUYER_FORECAST_BASE_YEAR = 2022
BUYER_FORECAST_BASE_YEAR_RATIONALE = (
    "FY2022 -- the last fiscal year that ENDED before the acquisition closed (J&J's "
    "FY2022 ended 1 January 2023; Abiomed closed 22 December 2022, leaving a nine-day "
    "stub J&J itself said was immaterial to 2022 results).\n\n"
    "This corrects a circularity that invalidated an earlier version of this model. "
    "Forecasting J&J's 'standalone' figures from the latest available base year "
    "(FY2025) uses history in which Abiomed is ALREADY CONSOLIDATED -- J&J's reported "
    "FY2023 onward includes Abiomed's revenue, its earnings, and the purchase "
    "accounting from this very transaction. Adding Abiomed's contribution on top of "
    "that in the pro-forma bridge double-counts the target, and worse, makes the "
    "'standalone' counterfactual meaningless: you cannot ask 'what would J&J have "
    "earned WITHOUT Abiomed' using a series that already has Abiomed in it.\n\n"
    "Consequence, stated plainly: forecasting from FY2022 means years 1-5 are "
    "FY2023-FY2027, which is what the pro-forma bridge needs and what J&J's own "
    "disclosed guidance addresses (year one = 2023, '$0.05 accretive' = 2024). It also "
    "means the forecast is a genuine counterfactual projection rather than a "
    "near-term extrapolation -- less accurate as a prediction of what J&J actually "
    "earned, but the only construction that answers the question this model asks.\n\n"
    "Supersedes the earlier lookback-window analysis in "
    "BUYER_DRIVER_WINDOW_RATIONALE, which was answering 'what is J&J's forward growth "
    "from today' -- the wrong question for a 2022 deal. With a FY2022 base the "
    "five-year window is FY2018-FY2022 (FY2020 absent, see the Trellis year-gap note), "
    "which sits entirely BEFORE the Kenvue separation, so the exclusion of FY2022-2023 "
    "designed for a FY2025 base does not apply and is not used here.\n\n"
    "RESOLVED, not merely assumed: an earlier pass flagged as an open question whether "
    "Trellis's revenue figures for these years are J&J's originally-filed consolidated "
    "totals or an already-restated continuing-operations basis. Confirmed as the "
    "latter -- see JNJ_CONTINUING_OPERATIONS_RESTATEMENT for the two primary sources. "
    "That means every year in this lookback window is measured consistently on the "
    "same (ex-Consumer-Health) basis, which is what makes a growth rate computed "
    "across them meaningful in the first place.")

FINANCING_SCENARIOS: tuple[tuple[str, float, str], ...] = (
    ("All cash on hand", 1.0,
     ("J&J held roughly $30bn+ in cash and marketable securities through 2022, so "
      "funding $17bn entirely from the balance sheet was feasible. Maximum foregone "
      "interest income, zero new interest expense.")),
    ("Half cash, half new debt", 0.5,
     ("The middle case. No evidence favours it specifically -- included to show "
      "whether the answer moves monotonically across the range.")),
    ("All new debt", 0.0,
     ("Preserves cash, maximum new interest expense, zero foregone interest income. "
      "Plausible for an A-rated issuer in a period when J&J was also managing the "
      "Kenvue separation and its associated capital structure changes.")),
)

BUYER_DRIVER_EXCLUDE_YEARS = {2022, 2023}
BUYER_DRIVER_WINDOW_RATIONALE = (
    "Revenue growth is materially sensitive to the lookback window -- 3.34% (unadjusted "
    "5yr) to 8.52% (3yr) across four windows tested via scripts/diagnose_jnj_kenvue.py, "
    "a 5.17-point spread too large to leave to whichever default Trellis happens to "
    "apply. Chose a 5-year lookback EXCLUDING 2022 and 2023 (-> 6.80% revenue growth) "
    "over the alternatives for two reasons, one directly evidenced and one inferred: "
    "(1) DIRECT: J&J's Kenvue separation closed August 2023 (a mid-year event), so "
    "FY2023's reported revenue mechanically reflects only a partial year of the "
    "consumer-health business that left -- a real distortion to any YoY comparison "
    "spanning that year, needing no further citation beyond the completion date itself. "
    "(2) INFERRED, not confirmed by a located citation: FY2022's -4.7% revenue decline "
    "plausibly reflects COVID-19 vaccine revenue rolling off a 2021 high and a "
    "historically strong US dollar that year depressing reported (not operational) "
    "international sales -- both are real, disclosed phenomena for J&J in this period "
    "generally, but this file did not locate a citation tying them to the specific "
    "-4.7% figure, so this half of the reasoning is weaker than the first. Rejected the "
    "3yr window (8.52%) despite it scoring highest: it still uses FY2023 as an endpoint "
    "and partly reflects a bounce off FY2022's depressed base rather than a clean "
    "post-transition trend. Rejected the 2yr window (6.05%) as too thin on its own by "
    "the same single-year-fragility logic Trellis's own 5yr default is built to avoid. "
    "Upgrade path: J&J discloses restated continuing-operations (ex-Consumer Health) "
    "historicals specifically to make this comparison clean -- pulling that series "
    "would convert this whole judgment call into a sourced one.")

TARGET_NORMALISED_OPERATING_INCOME_FY2022 = demonstrated(
    "target_normalised_operating_income_fy2022_mm", 140.720 + 115.986,
    f"$140.720mm reported operating income PLUS the $115.986mm one-time acquired-IPR&D "
    f"charge disclosed in the same statement = $256.706mm normalised. "
    f"{ABIOMED_10K_FY2022}. Growing the REPORTED figure forward -- as an earlier "
    f"version of this model did -- projects a permanently depressed earnings base off "
    f"a charge that by definition does not recur, understating the target's "
    f"contribution in every forecast year. The charge is sourced in "
    f"TARGET_OPERATING_INCOME_FY2022's own citation; normalising it is a judgment, so "
    f"this is DEMONSTRATED (arithmetic on two sourced figures), not SOURCED. Note the "
    f"reported figure is retained above and still used wherever the actual as-filed "
    f"number is wanted.")

TARGET_FISCAL_YEAR_END_MONTH = 3
BUYER_FISCAL_YEAR_END_MONTH = 12
TARGET_CALENDARIZATION_NOTE = (
    "Abiomed reported on a 31 March fiscal year end; J&J on ~31 December. Abiomed's "
    "FY2022 covers April 2021 - March 2022, of which only three months fall inside "
    "J&J's calendar 2022. Combining the two without adjustment misstates the "
    "contributed period by a nine-month offset -- on a target growing ~22% a year, "
    "roughly a sixth of contributed revenue. deallab.calendarize exists for exactly "
    "this and is applied in scripts/run_jnj_abiomed.py rather than left as an unused "
    "module. Because only one Abiomed fiscal year is sourced here, the calendarization "
    "is applied to the PROJECTED series (built from that base) rather than to two "
    "sourced adjacent years -- weaker than the two-year interpolation the module "
    "supports, and flagged as such at the point of use.")

MISSING: tuple[Input, ...] = (
    unsourced("cvr_acquisition_date_fair_value",
              "J&J FY2022 10-K business combination footnote: the specific booked fair "
              "value of the CVR liability at acquisition, at the finest grain J&J "
              "discloses it -- distinct from the $1.6bn undiscounted aggregate maximum "
              "(ACTUAL_PPA) and from the ~$865mm/0.541 estimate now used for "
              "CVR.probability_weight (see that input's own citation: two convergent "
              "but still circumstantial triangulations, not a verbatim disclosed "
              "figure). Finding this footnote replaces an assumption with a fact and "
              "should be treated as higher priority than its position in this list "
              "suggests -- though with two independent estimates now converging within "
              "5 points of each other, the practical stakes of finding it have fallen "
              "since this item was first opened."),
)

__all__ = [
               "ABIOMED_10K_FY2022",
               "ABIOMED_10Q_JUN2022",
               "ABIOMED_PR_AUG2022",
               "ACTUAL_PPA",
               "ACTUAL_PPA_SOURCE",
               "ADVISORY_FEES_PRETAX",
               "ANNOUNCE_8K",
               "BUYER_DILUTED_SHARES",
               "BUYER_DRIVER_EXCLUDE_YEARS",
               "BUYER_DRIVER_LOOKBACK_YEARS",
               "BUYER_DRIVER_WINDOW_RATIONALE",
               "BUYER_FISCAL_YEAR_END_MONTH",
               "BUYER_FORECAST_BASE_YEAR",
               "BUYER_FORECAST_BASE_YEAR_RATIONALE",
               "BUYER_TAX_RATE_OVERRIDE",
               "CLOSE_8K",
               "CVR",
               "DEFERRED_TAX_LIABILITY_ABIOMED",
               "EV_RESTATEMENT_NOTE",
               "FINANCING_MIX_NOT_DISCLOSED",
               "FINANCING_SCENARIOS",
               "GUIDANCE",
               "GUIDANCE_2024_ACCRETION_USD",
               "GUIDANCE_YEAR_ONE_BOUNDS",
               "INTANGIBLE_AMORTIZABLE_FV",
               "IPRD_FV",
               "JNJ_10K_FY2024",
               "JNJ_10K_FY2024_ACQUISITION_TOTAL",
               "JNJ_10K_FY2024_OTHER_EXPENSE_NOTE",
               "JNJ_10Q_Q1_2023",
               "JNJ_ADJUSTED_TAX_RATE_DISCLOSURES",
               "JNJ_CONTINUING_OPERATIONS_RESTATEMENT",
               "MARKETABLE_SECURITIES_ACQUIRED",
               "MISSING",
               "PPA_MEASUREMENT_PERIOD_ADJUSTMENT",
               "TARGET_BOOK_EQUITY",
               "TARGET_CALENDARIZATION_NOTE",
               "TARGET_EFFECTIVE_TAX_RATE_FY2022",
               "TARGET_FISCAL_YEAR_END_MONTH",
               "TARGET_NET_DEBT",
               "TARGET_NET_INCOME_FY2022",
               "TARGET_NORMALISED_OPERATING_INCOME_FY2022",
               "TARGET_OPERATING_INCOME_FY2022",
               "TARGET_REVENUE_FY2022",
               "TERMS",
               "TOTAL_LIABILITIES_ASSUMED_ESTIMATE",
               "UPFRONT_NET_OF_CASH_ACQUIRED",
]
