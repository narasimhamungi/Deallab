"""
Checking the model against what the buyer actually told the market.

This is the module that distinguishes modelling a real closed deal from modelling a
hypothetical. A hypothetical has no answer key: it can be internally consistent and
still be nonsense, and nothing in the model will say so. A real deal with disclosed
EPS guidance has an external check, and the model either lands near it or has to explain
why not.

Two disciplines make the check honest rather than decorative.

**The comparison must be like for like.** Buyer guidance is on an adjusted basis and is
typically stated including financing impact. Comparing it to a GAAP figure, or to an
adjusted figure computed with a different exclusion list, produces a gap that means
nothing. `check` takes the basis explicitly and refuses to guess.

**A miss is a finding, not a failure to be tuned away.** The temptation on seeing a gap
is to adjust an assumption until the model agrees with guidance. That is curve-fitting,
and it destroys the check: a model tuned to reproduce guidance can no longer test it.
The correct response to a gap is to identify which input drives it and state that the
model implies something different from what management said. Management guidance is
itself a forecast made by people with an interest in the deal looking good -- agreement
is evidence the model is reasonable, disagreement is a hypothesis about which assumption
is wrong, on either side.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GuidanceCheck:
    label: str
    basis: str
    guided: str
    guided_low: float | None
    guided_high: float | None
    modelled: float
    within: bool | None
    gap: float | None
    reading: str

    def format(self) -> str:
        status = {True: "WITHIN GUIDANCE", False: "OUTSIDE GUIDANCE",
                  None: "NOT NUMERICALLY COMPARABLE"}[self.within]
        # Displayed to 2 decimals as a PERCENTAGE, not 3 decimals as a raw fraction.
        # -0.0102 formatted as "+.3f" prints "-0.010" -- visually identical to a -0.01
        # boundary it has actually just missed by 2 basis points. That rounding hid the
        # exact finding this check exists to surface on a real run: one financing
        # scenario landed 2bp outside guidance while others missed by 50-90bp. Fixed to
        # show the precision the comparison actually turns on.
        lines = [f"  {self.label} [{self.basis}] -- {status}",
                 f"    Guided:   {self.guided}",
                 f"    Modelled: {self.modelled:+.2%}"]
        if self.gap is not None:
            lines.append(f"    Gap:      {self.gap:+.2%} "
                         f"({self.gap * 10_000:+.0f}bp)")
        lines.append(f"    {self.reading}")
        return "\n".join(lines)


def check_range(label: str, basis: str, guided_text: str,
                guided_low: float, guided_high: float,
                modelled: float, units: str = "") -> GuidanceCheck:
    """Compare a modelled figure against a guided range."""
    within = guided_low <= modelled <= guided_high
    if within:
        gap = 0.0
        reading = ("The model reproduces disclosed guidance without being fitted to it. "
                   "That is the check passing -- it does not make the assumptions "
                   "correct, only mutually consistent with what management expected.")
    else:
        gap = (modelled - guided_high) if modelled > guided_high else (modelled - guided_low)
        direction = "more favourable than" if modelled > guided_high else "worse than"
        reading = (f"The model is {abs(gap):.2%}{units} {direction} guidance "
                  f"({abs(gap) * 10_000:.0f}bp). Do not "
                   f"tune an input to close this. Identify which assumption drives it -- "
                   f"most often the financing mix, the intangible amortisation life, or "
                   f"the synergy phase-in -- and state the disagreement. Management "
                   f"guidance is a forecast by an interested party; the model disagreeing "
                   f"with it is a hypothesis, not automatically an error.")
    return GuidanceCheck(label, basis, guided_text, guided_low, guided_high,
                         modelled, within, gap, reading)


def check_point(label: str, basis: str, guided_text: str, guided: float,
                modelled: float, tolerance: float, units: str = "") -> GuidanceCheck:
    """Compare against a point estimate with an explicit tolerance.

    The tolerance is a parameter because 'approximately $0.05' carries different
    precision depending on the buyer's EPS base. Hardcoding a tolerance would let the
    check quietly define its own pass mark.
    """
    gap = modelled - guided
    within = abs(gap) <= tolerance
    reading = (f"Within the stated {tolerance:.3f}{units} tolerance."
               if within else
               f"Outside the {tolerance:.3f}{units} tolerance. The direction matters: "
               f"a model more accretive than management guided usually means the "
               f"synergy phase-in is too fast or the financing cost too low; less "
               f"accretive usually means the amortisation life is too short or the "
               f"purchase price allocation too intangible-heavy.")
    return GuidanceCheck(label, basis, guided_text, guided - tolerance, guided + tolerance,
                         modelled, within, gap, reading)


@dataclass(frozen=True)
class GuidanceReport:
    checks: tuple[GuidanceCheck, ...]

    @property
    def all_within(self) -> bool:
        return all(c.within for c in self.checks if c.within is not None)

    def format(self) -> str:
        lines = ["MODEL vs. DISCLOSED GUIDANCE", "=" * 72]
        for c in self.checks:
            lines.append(c.format())
            lines.append("")
        lines.append("  A model that matches guidance on every line should be viewed "
                     "with suspicion, not satisfaction -- it usually means an input was "
                     "chosen to produce the match.")
        return "\n".join(lines)
