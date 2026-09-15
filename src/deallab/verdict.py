"""
Does this acquisition create value for the buyer?

The question has two answers and they are not the same question. This module computes
both and refuses to combine them. There is no `overall_score`, no weighted blend, no
single boolean. That refusal is the design -- ValuationLab's finding was that averaging
methods deletes the only informative part, and the same holds here with more force,
because the two lenses answer different questions and a deal can genuinely pass one and
fail the other.

**The accounting lens** asks: what happens to reported EPS? It is the question the
market reacts to on announcement day and the one management guides on. It is also
substantially an artefact of relative P/E and funding cost. A buyer with a high multiple
can acquire almost any lower-multiple target with debt and show accretion, having created
nothing.

**The economic lens** asks: did the buyer pay less than the thing is worth to them? That
is premium paid versus the present value of what the premium buys. It is the question
that determines whether shareholders are better off, and it is the one that gets
answered three years late, in an impairment charge.

The bridge between the two is the **unexplained premium**: price paid, less the target's
standalone intrinsic value, less the present value of synergies that have actually been
identified. Whatever is left is the amount the buyer is paying for benefits nobody has
named. Stating that number is the single most useful thing this model does, and it is
the thing a generic merger template structurally cannot produce, because it has no
standalone valuation to net against -- it takes the price as given.

That standalone value comes from ValuationLab, and it arrives carrying ValuationLab's
own judgement about whether its methods were fit to produce it. If ValuationLab
disqualified every method for the target, the economic lens says so and declines to
compute a premium, rather than quietly using a number it already flagged as unreliable.
"""

from __future__ import annotations

from dataclasses import dataclass

from .accretion import AccretionResult, BreakevenSynergies


@dataclass(frozen=True)
class AccountingVerdict:
    """What the deal does to reported earnings. Not a judgement about value."""
    year_one: AccretionResult
    later_years: tuple[AccretionResult, ...]
    breakeven: BreakevenSynergies
    first_accretive_year: int | None
    reading: str

    def format(self) -> str:
        lines = ["ACCOUNTING LENS -- effect on reported EPS", "=" * 72]
        for r in (self.year_one,) + self.later_years:
            lines.append(f"  Year {r.year_index}: adjusted {r.adjusted_pct:+.2%} "
                         f"({r.adjusted_verdict}), GAAP {r.gaap_pct:+.2%} "
                         f"({r.gaap_verdict})")
        if self.first_accretive_year:
            lines.append(f"  First adjusted-accretive year: {self.first_accretive_year}")
        else:
            lines.append("  Never adjusted-accretive within the modelled horizon.")
        lines.append("")
        lines.append(f"  Breakeven synergy ({self.breakeven.basis}, year "
                     f"{self.breakeven.year_index}): "
                     f"${self.breakeven.required_pretax:,.0f}mm pre-tax required")
        lines.append(f"  {self.breakeven.reading}")
        lines.append("")
        lines.append(f"  {self.reading}")
        return "\n".join(lines)


@dataclass(frozen=True)
class EconomicVerdict:
    """Whether the buyer paid less than the acquisition is worth to it."""
    price_paid: float                    # total consideration incl. CVR at FV
    standalone_value: float | None       # from ValuationLab, or None if unfit
    standalone_basis: str                # which method anchored it, and its caveat
    premium_paid: float | None
    synergy_npv: float | None
    synergy_npv_ex_revenue: float | None
    unexplained_premium: float | None
    unexplained_as_pct_of_price: float | None
    irr: float | None
    wacc: float | None
    warnings: tuple[str, ...]
    reading: str

    def format(self) -> str:
        lines = ["ECONOMIC LENS -- did the buyer pay less than it is worth?", "=" * 72,
                 f"  Price paid (incl. contingent at FV)   ${self.price_paid:>12,.0f}mm"]
        if self.standalone_value is None:
            lines.append("  Standalone value                      UNAVAILABLE")
            lines.append(f"  {self.standalone_basis}")
        else:
            lines.append(f"  Target standalone value               ${self.standalone_value:>12,.0f}mm")
            lines.append(f"    basis: {self.standalone_basis}")
            lines.append(f"  Premium paid                          ${self.premium_paid:>12,.0f}mm")
            lines.append(f"  Less PV of identified synergies       ${-(self.synergy_npv or 0):>12,.0f}mm")
            lines.append(f"  = UNEXPLAINED PREMIUM                 ${self.unexplained_premium:>12,.0f}mm "
                         f"({self.unexplained_as_pct_of_price:+.1%} of price)")
            if self.synergy_npv_ex_revenue is not None:
                ex = self.premium_paid - self.synergy_npv_ex_revenue
                lines.append(f"  Unexplained if revenue synergies fail ${ex:>12,.0f}mm")
        if self.irr is not None and self.wacc is not None:
            spread = self.irr - self.wacc
            lines.append(f"  IRR {self.irr:.2%} vs. WACC {self.wacc:.2%}: {spread:+.2%} spread")
        for w in self.warnings:
            lines.append(f"  ! {w}")
        lines.append("")
        lines.append(f"  {self.reading}")
        return "\n".join(lines)


@dataclass(frozen=True)
class DealVerdict:
    """Both lenses, side by side. Deliberately has no combined score.

    If you want one number, you have to choose which question you are asking, and
    choosing is the analyst's job, not the model's.
    """
    accounting: AccountingVerdict
    economic: EconomicVerdict
    disagreement: str

    def format(self) -> str:
        parts = [self.accounting.format(), "", self.economic.format()]
        if self.disagreement:
            parts += ["", "LENS DISAGREEMENT", "=" * 72, "  " + self.disagreement]
        return "\n".join(parts)


def build_accounting_verdict(results: list[AccretionResult],
                             breakeven: BreakevenSynergies) -> AccountingVerdict:
    if not results:
        raise ValueError("No accretion results supplied.")
    ordered = sorted(results, key=lambda r: r.year_index)
    first = next((r.year_index for r in ordered if r.adjusted_pct > 0.01), None)

    y1 = ordered[0]
    gap = y1.adjusted_pct - y1.gaap_pct
    reading = (
        f"On an adjusted basis year one is {y1.adjusted_verdict} at {y1.adjusted_pct:+.2%}; "
        f"on GAAP it is {y1.gaap_verdict} at {y1.gaap_pct:+.2%}. The {gap:.2%} gap between "
        f"them is purchase accounting -- non-cash, real to reported earnings, and excluded "
        f"by the buyer's own adjusted definition. Neither figure says anything about "
        f"whether the price was right; see the economic lens.")
    return AccountingVerdict(y1, tuple(ordered[1:]), breakeven, first, reading)


def build_economic_verdict(price_paid: float, standalone_value: float | None,
                           standalone_basis: str, synergy_npv: float | None,
                           synergy_npv_ex_revenue: float | None = None,
                           irr: float | None = None, wacc: float | None = None,
                           extra_warnings: tuple[str, ...] = ()) -> EconomicVerdict:
    warnings = list(extra_warnings)

    if standalone_value is None:
        return EconomicVerdict(
            price_paid=price_paid, standalone_value=None,
            standalone_basis=standalone_basis, premium_paid=None,
            synergy_npv=synergy_npv, synergy_npv_ex_revenue=synergy_npv_ex_revenue,
            unexplained_premium=None, unexplained_as_pct_of_price=None,
            irr=irr, wacc=wacc, warnings=tuple(warnings),
            reading=("No standalone valuation was fit to anchor a premium, so the "
                     "economic question cannot be answered here. That is a finding, "
                     "not a gap: a premium measured against a valuation its own author "
                     "disqualified is worse than no premium at all. Either widen the "
                     "target's peer set, or accept that the deal has to be judged on "
                     "the synergy case and the returns alone."),
        )

    premium = price_paid - standalone_value
    syn = synergy_npv or 0.0
    unexplained = premium - syn
    pct = unexplained / price_paid if price_paid else 0.0

    if premium < 0:
        warnings.append(
            "Price is below standalone value. For a public target with a control "
            "premium that is unusual enough to check the standalone valuation before "
            "believing it.")
    if syn > premium * 2 and premium > 0:
        warnings.append(
            "Synergy NPV is more than twice the premium paid. Either the target was "
            "acquired remarkably cheaply or the synergy case is doing too much work; "
            "re-run excluding revenue synergies before relying on this.")

    if unexplained <= 0:
        reading = (
            f"The identified synergies alone (${syn:,.0f}mm PV) cover the "
            f"${premium:,.0f}mm premium. The deal does not require benefits nobody has "
            f"named -- which is rare, and is the strongest form the economic case can "
            f"take. It still depends entirely on the synergies actually arriving.")
    else:
        reading = (
            f"After crediting every identified synergy at present value "
            f"(${syn:,.0f}mm), ${unexplained:,.0f}mm of the price -- {pct:.1%} -- is "
            f"unaccounted for. That is the amount being paid for benefits that have not "
            f"been articulated: option value on the pipeline, strategic positioning, or "
            f"overpayment. All three look identical in a model; only the first two are "
            f"defensible, and neither has been demonstrated here.")

    if irr is not None and wacc is not None and irr < wacc:
        reading += (f" The {wacc - irr:.2%} shortfall of IRR against WACC points the "
                    f"same way independently.")

    return EconomicVerdict(
        price_paid=price_paid, standalone_value=standalone_value,
        standalone_basis=standalone_basis, premium_paid=premium,
        synergy_npv=synergy_npv, synergy_npv_ex_revenue=synergy_npv_ex_revenue,
        unexplained_premium=unexplained, unexplained_as_pct_of_price=pct,
        irr=irr, wacc=wacc, warnings=tuple(warnings), reading=reading,
    )


def build(accounting: AccountingVerdict, economic: EconomicVerdict) -> DealVerdict:
    """Assemble both lenses and name the disagreement, if there is one."""
    disagreement = ""
    acc_positive = accounting.year_one.adjusted_pct > 0.01
    econ_positive = (economic.unexplained_premium is not None
                     and economic.unexplained_premium <= 0)

    if acc_positive and economic.unexplained_premium is not None and not econ_positive:
        disagreement = (
            f"The lenses disagree, and this is the most common shape of a value-"
            f"destroying acquisition: EPS accretive from year one, yet "
            f"${economic.unexplained_premium:,.0f}mm of the price unexplained by any "
            f"identified benefit. Accretion here is financed by the funding structure, "
            f"not earned by the combination. A deal in this quadrant will look "
            f"successful in guidance and appear years later as a goodwill impairment.")
    elif not acc_positive and econ_positive:
        disagreement = (
            "The lenses disagree in the direction that usually favours proceeding: "
            "near-term EPS dilution, but a premium fully covered by identified "
            "synergies. Dilution driven by purchase accounting and financing timing is "
            "a reporting outcome; the economics are the decision. This is the quadrant "
            "where management has to be willing to take the guidance hit.")
    elif acc_positive and econ_positive:
        disagreement = ("Both lenses point the same way. Attack the synergy phase-in "
                        "and the standalone valuation before trusting the agreement -- "
                        "concurrence between two lenses fed by the same assumptions is "
                        "not independent confirmation.")
    elif not acc_positive and economic.unexplained_premium is not None and not econ_positive:
        disagreement = ("Both lenses point the same way, against the deal. There is no "
                        "tension to resolve and no reading under which this creates "
                        "value as modelled.")
    return DealVerdict(accounting, economic, disagreement)
