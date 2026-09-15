"""
Accretion / dilution -- and the two things that make it worth computing.

Accretion/dilution on its own is a weak signal. It is a function of relative P/E and
funding cost, and a deal can be accretive purely because debt is cheaper than the
buyer's earnings yield, with no value created at all. Reporting "+2.1% accretive" as a
conclusion is the standard failure of merger-model output.

This module therefore computes three things, and the second and third are the ones that
carry information:

1. **Accretion/dilution, GAAP and adjusted, separately.** Never averaged, never merged.
   A deal that is adjusted-accretive and GAAP-dilutive is the normal case for an
   intangible-heavy acquisition, and the gap between the two is the size of the
   purchase accounting, which is a fact about the deal worth stating.

2. **Breakeven synergies.** Invert the arithmetic: what annual run-rate pre-tax synergy
   is required to hold EPS flat? That single number converts an opinion ("management
   says $X of synergies") into a testable claim ("the price requires $Y; management has
   identified $X"). If required exceeds identified, the deal needs synergies nobody has
   named. This is the most useful number in the entire model and most templates do not
   produce it.

3. **Source attribution.** Decompose the EPS change into the target's contribution, the
   synergies, the financing cost and the purchase accounting. A deal that is accretive
   only because of cheap debt looks identical to one accretive on operating merit until
   you split them.
"""

from __future__ import annotations

from dataclasses import dataclass

from .proforma import ProFormaYear


@dataclass(frozen=True)
class AccretionResult:
    year_index: int
    standalone_eps: float
    gaap_pro_forma_eps: float
    adjusted_pro_forma_eps: float
    gaap_delta_eps: float
    adjusted_delta_eps: float
    gaap_pct: float
    adjusted_pct: float
    attribution: dict[str, float]   # EPS impact by driver, adjusted basis
    purchase_accounting_gap_eps: float

    @property
    def gaap_verdict(self) -> str:
        return _verdict(self.gaap_pct)

    @property
    def adjusted_verdict(self) -> str:
        return _verdict(self.adjusted_pct)

    def format(self) -> str:
        lines = [
            f"ACCRETION / DILUTION -- year {self.year_index}",
            "-" * 62,
            f"  Buyer standalone EPS                  ${self.standalone_eps:>8.3f}",
            (f"  Pro-forma EPS (adjusted)              ${self.adjusted_pro_forma_eps:>8.3f}  "
             f"{self.adjusted_delta_eps:+.3f}  ({self.adjusted_pct:+.2%}) -- {self.adjusted_verdict}"),
            (f"  Pro-forma EPS (GAAP)                  ${self.gaap_pro_forma_eps:>8.3f}  "
             f"{self.gaap_delta_eps:+.3f}  ({self.gaap_pct:+.2%}) -- {self.gaap_verdict}"),
            (f"  Purchase accounting gap               ${self.purchase_accounting_gap_eps:>8.3f} "
             f"per share -- the whole distance between the two lines above"),
            "",
            "  EPS impact by driver (adjusted basis):",
        ]
        for k, v in sorted(self.attribution.items(), key=lambda kv: -abs(kv[1])):
            lines.append(f"    {k:<52} {v:+.4f}")
        return "\n".join(lines)


def _verdict(pct: float) -> str:
    if pct > 0.01:
        return "accretive"
    if pct < -0.01:
        return "dilutive"
    return "broadly neutral"


def compute(pf: ProFormaYear, standalone_net_income: float,
            standalone_shares: float) -> AccretionResult:
    """Compare pro-forma EPS to what the buyer would have earned alone.

    The comparison is always against the buyer's OWN standalone EPS in the same year --
    not against the prior year, and not against consensus. Anything else measures
    something other than the deal.
    """
    standalone_eps = standalone_net_income / standalone_shares

    gaap_eps = pf.gaap_eps
    adj_eps = pf.adjusted_eps

    attribution: dict[str, float] = {}
    for step in pf.steps:
        if not step.in_adjusted:
            continue
        attribution[step.label] = step.amount / pf.adjusted_shares
    dilution_from_shares = (standalone_net_income / pf.adjusted_shares) - standalone_eps
    if abs(dilution_from_shares) > 1e-9:
        attribution["Share count dilution from equity issued"] = dilution_from_shares

    return AccretionResult(
        year_index=pf.year_index,
        standalone_eps=standalone_eps,
        gaap_pro_forma_eps=gaap_eps,
        adjusted_pro_forma_eps=adj_eps,
        gaap_delta_eps=gaap_eps - standalone_eps,
        adjusted_delta_eps=adj_eps - standalone_eps,
        gaap_pct=(gaap_eps - standalone_eps) / standalone_eps,
        adjusted_pct=(adj_eps - standalone_eps) / standalone_eps,
        attribution=attribution,
        purchase_accounting_gap_eps=adj_eps - gaap_eps,
    )


@dataclass(frozen=True)
class BreakevenSynergies:
    year_index: int
    basis: str                       # "adjusted" or "GAAP"
    required_after_tax: float        # USD millions
    required_pretax: float           # USD millions
    identified_pretax_this_year: float
    shortfall_pretax: float          # required - identified; positive = gap
    as_pct_of_target_revenue: float | None
    reading: str


def breakeven_synergies(pf: ProFormaYear, standalone_net_income: float,
                        standalone_shares: float, tax_rate: float,
                        realised_pretax_synergies: float,
                        target_revenue: float | None = None,
                        basis: str = "adjusted") -> BreakevenSynergies:
    """Annual pre-tax synergy required to hold EPS flat in this year.

    Solved by removing the synergies actually modelled and asking what would have to
    replace them. Expressed as a percentage of target revenue as well, because that is
    the form in which synergy claims are usually benchmarked -- and because a required
    figure above roughly 10% of target revenue is, for most strategic acquisitions, a
    claim that should not survive a committee.
    """
    if basis not in ("adjusted", "GAAP"):
        raise ValueError("basis must be 'adjusted' or 'GAAP'")

    standalone_eps = standalone_net_income / standalone_shares
    pf_ni = pf.adjusted_net_income if basis == "adjusted" else pf.gaap_net_income
    shares = pf.adjusted_shares if basis == "adjusted" else pf.gaap_shares

    # After-tax income needed to lift pro-forma EPS back to standalone EPS.
    target_ni = standalone_eps * shares
    realised_after_tax = realised_pretax_synergies * (1 - tax_rate)
    gap_after_tax = target_ni - pf_ni
    required_after_tax = realised_after_tax + gap_after_tax
    required_pretax = required_after_tax / (1 - tax_rate) if tax_rate < 1 else float("inf")

    shortfall = required_pretax - realised_pretax_synergies
    pct_rev = required_pretax / target_revenue if target_revenue else None

    if required_pretax <= 0:
        reading = ("The deal holds EPS flat with zero synergies on this basis -- "
                   "accretion here is arithmetic (earnings bought cheaply relative to "
                   "funding cost), not operating performance. That is not the same as "
                   "value creation; see the economic lens.")
    elif shortfall <= 0:
        reading = (f"Identified synergies of ${realised_pretax_synergies:,.0f}mm this "
                   f"year already exceed the ${required_pretax:,.0f}mm required for "
                   f"EPS neutrality. The accounting case does not depend on synergies "
                   f"that have not been named.")
    else:
        reading = (f"The price requires ${required_pretax:,.0f}mm of pre-tax synergy "
                   f"this year to hold EPS flat; ${realised_pretax_synergies:,.0f}mm is "
                   f"modelled. The ${shortfall:,.0f}mm difference is the part of the "
                   f"deal resting on benefits nobody has identified"
                   + (f" -- {pct_rev:.1%} of target revenue." if pct_rev else "."))

    return BreakevenSynergies(
        year_index=pf.year_index, basis=basis,
        required_after_tax=required_after_tax, required_pretax=required_pretax,
        identified_pretax_this_year=realised_pretax_synergies,
        shortfall_pretax=shortfall, as_pct_of_target_revenue=pct_rev,
        reading=reading,
    )
