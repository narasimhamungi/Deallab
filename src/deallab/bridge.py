"""
The seam between DealLab and the two packages upstream of it.

DealLab consumes ValuationLab as an installed package, which consumes Trellis the same
way. The chain is deliberate: fundamentals come out of SEC XBRL once, through one
pipeline, and every layer above inherits that provenance rather than re-sourcing it.

Three jobs here, and the first is the important one.

**Standalone value carries its own fitness.** ValuationLab does not return a number; it
returns a `Conclusion` containing an `AnchorRecommendation` that disqualifies methods on
measured thresholds. This bridge honours that. If ValuationLab found nothing fit to
anchor, `standalone_value` returns None and the economic lens says the premium cannot be
measured -- it does not fall back to the DCF midpoint, or to an average of whatever
ranges exist. Reaching past an upstream disqualification to grab a number anyway would
undo the entire point of the upstream module.

**Price is never derived.** Nothing here asks ValuationLab what the target is worth in
order to set the purchase price. The price is a sourced fact from the merger agreement.
ValuationLab's output is the benchmark the price is measured against. Getting this
backwards -- letting the valuation set the price and then checking accretion against it
-- produces a model that can never find a deal expensive.

**Precedents are cited, never pooled.** ValuationLab's finding was that a single blended
pharma multiple does not exist: J&J/Actelion at 12.3x EV/Revenue and BMS/Celgene at 4.8x
sit in the same tier and are 2.5x apart. `precedent_check` therefore takes exactly one
`PrecedentDeal` and refuses a list. If you want two comparisons, run it twice and look
at both -- which is the behaviour that produced the finding in the first place.

Imports are lazy so the rest of DealLab is testable without the upstream packages
installed. A missing upstream raises a specific error at the point of use rather than an
ImportError at module load.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .proforma import StandaloneYear


class UpstreamUnavailable(RuntimeError):
    pass


def _require(module: str):
    try:
        __import__(module)
    except ImportError as e:  # pragma: no cover - environment dependent
        raise UpstreamUnavailable(
            f"{module} is not installed. DealLab consumes ValuationLab as a package "
            f"(which consumes Trellis): pip install "
            f"git+https://github.com/narasimhamungi/valuationlab.git") from e
    import sys
    return sys.modules[module]


# --- Standalone value ---------------------------------------------------------------

@dataclass(frozen=True)
class StandaloneValue:
    enterprise_value: float | None
    low: float | None
    high: float | None
    basis: str
    fit: bool


def standalone_value(conclusion: Any) -> StandaloneValue:
    """Extract a usable standalone value from a ValuationLab `Conclusion`.

    Uses `conclusion.anchor_method` -- the analyst's stated anchor if one was given,
    otherwise ValuationLab's derived recommendation. If neither exists, the target has
    no method fit to anchor and this returns fit=False with the reason, which the
    economic lens is built to handle as a finding rather than an error.
    """
    method = conclusion.anchor_method
    if method is None:
        rec = conclusion.recommendation
        disqualified = "; ".join(
            f"{d.method.value}: {d.reason} ({d.measured})" for d in rec.disqualified)
        return StandaloneValue(
            None, None, None, fit=False,
            basis=(f"ValuationLab disqualified every method for this target. "
                   f"{disqualified or rec.rationale}"))

    rng = next((r for r in conclusion.ranges if r.method is method), None)
    if rng is None:
        return StandaloneValue(
            None, None, None, fit=False,
            basis=f"Anchor method {method.value} has no range in the conclusion.")

    conflict = f" ANCHOR CONFLICT: {conclusion.anchor_conflict}" if conclusion.anchor_conflict else ""
    return StandaloneValue(
        enterprise_value=rng.mid, low=rng.low, high=rng.high, fit=True,
        basis=(f"{method.value} midpoint, range {rng.low:,.0f}-{rng.high:,.0f}. "
               f"{rng.basis}. Caveat carried from ValuationLab: {rng.caveat}"
               f"{conflict}"),
    )


# --- Trellis forecast -> pro-forma input --------------------------------------------

def standalone_year_from_trellis(forecast_year: dict, year_index: int) -> StandaloneYear:
    """Map one year of a Trellis forecast dict onto the pro-forma input shape.

    Trellis's `run_forecast` returns {fiscal_year: {canonical_name: value}} using the
    canonical names in its schema. Keys are read by name and a missing one raises, so a
    schema change upstream surfaces immediately rather than silently zeroing a line.

    Units: Trellis works in reporting units (dollars, as filed). DealLab works in USD
    millions throughout. Conversion is the caller's responsibility and is deliberately
    not done here -- a unit conversion buried in an adapter is exactly the kind of
    silent 1,000,000x error this portfolio's own principles warn about.
    """
    required = ("revenue", "operating_income", "net_income")
    missing = [k for k in required if k not in forecast_year]
    if missing:
        raise KeyError(
            f"Trellis forecast year is missing {missing}. Expected canonical names from "
            f"trellis.schema. Present: {sorted(forecast_year)}")
    return StandaloneYear(
        year_index=year_index,
        revenue=forecast_year["revenue"],
        operating_income=forecast_year["operating_income"],
        net_income=forecast_year["net_income"],
        depreciation_amortisation=forecast_year.get("depreciation_amortization", 0.0),
    )


# --- Precedent discipline -----------------------------------------------------------

@dataclass(frozen=True)
class PrecedentCheck:
    deal_label: str
    deal_ev_revenue: float
    deal_ev_ebitda_proxy: float
    subject_ev_revenue: float
    subject_ev_ebitda_proxy: float | None
    revenue_multiple_gap: float
    reading: str
    source: str


def precedent_check(deal: Any, subject_ev: float, subject_revenue: float,
                    subject_ebitda_proxy: float | None = None) -> PrecedentCheck:
    """Compare this transaction's multiples against exactly ONE sourced precedent.

    Takes a single `valuationlab.precedent.PrecedentDeal`, never a list. A function that
    accepted a list would immediately be used to average one, and ValuationLab's
    precedent module exists specifically to demonstrate that averaging destroys the
    information.
    """
    if isinstance(deal, (list, tuple, set)):
        raise TypeError(
            "precedent_check takes one PrecedentDeal, not a collection. Pooling "
            "precedent multiples is the practice ValuationLab measured as wrong: "
            "J&J/Actelion and BMS/Celgene sit in the same tier 2.5x apart on "
            "EV/Revenue. Call this once per deal and read both results.")

    subj_rev_mult = subject_ev / subject_revenue
    subj_ebitda_mult = (subject_ev / subject_ebitda_proxy
                        if subject_ebitda_proxy else None)
    gap = subj_rev_mult / deal.ev_revenue - 1.0

    if abs(gap) < 0.20:
        reading = (f"This deal prices within 20% of {deal.acquirer}/{deal.target} on "
                   f"EV/Revenue ({subj_rev_mult:.1f}x vs {deal.ev_revenue:.1f}x). One "
                   f"comparison is corroboration, not a range -- it says this price is "
                   f"not an outlier against this specific deal, nothing more.")
    else:
        direction = "above" if gap > 0 else "below"
        reading = (f"This deal prices {abs(gap):.0%} {direction} "
                   f"{deal.acquirer}/{deal.target} on EV/Revenue ({subj_rev_mult:.1f}x "
                   f"vs {deal.ev_revenue:.1f}x). The gap is only meaningful if the two "
                   f"targets are comparable on growth and franchise concentration -- "
                   f"check that before reading it as expensive or cheap. "
                   f"{deal.notes}")

    return PrecedentCheck(
        deal_label=f"{deal.acquirer}/{deal.target} ({deal.announced})",
        deal_ev_revenue=deal.ev_revenue,
        deal_ev_ebitda_proxy=deal.ev_ebitda_proxy,
        subject_ev_revenue=subj_rev_mult,
        subject_ev_ebitda_proxy=subj_ebitda_mult,
        revenue_multiple_gap=gap,
        reading=reading,
        source=deal.source,
    )
