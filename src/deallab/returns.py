"""
The acquisition as an investment: IRR and MOIC.

A strategic buyer does not exit. Applying a sponsor's returns framework to a corporate
acquisition is therefore a deliberate borrowing, and it needs a stated justification
rather than being included because merger models usually have an IRR tab.

The justification: a strategic buyer's alternative use of the same capital is buying
back its own stock or paying down debt, both of which have known returns. Computing an
IRR on the acquisition -- with a terminal value struck at an explicitly stated exit
multiple, on the explicit assumption of a notional exit that will not occur -- makes the
comparison possible. An acquisition returning below the buyer's WACC is destroying value
regardless of what it does to EPS, and IRR is the cleanest way to say so.

The exit multiple is the weakest input in this module and probably in the whole model.
Setting exit equal to entry is the standard convention and it embeds a real assumption:
that none of the return comes from multiple expansion. That is the conservative choice
and it is the default here, but it is still an assumption and it is registered as one.

`irr` uses bisection rather than Newton's method. Newton is faster and fails silently on
the sign-change patterns that non-conventional cash flows produce. Bisection over a
bracketed range either converges or reports that it could not, which is the behaviour
this model wants everywhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise

from .provenance import AssumptionRegister, Input


class IRRError(RuntimeError):
    pass


def npv(rate: float, cash_flows: list[float]) -> float:
    """cash_flows[0] occurs at t=0."""
    return sum(cf / (1 + rate) ** t for t, cf in enumerate(cash_flows))


def irr(cash_flows: list[float], lo: float = -0.9999, hi: float = 10.0,
        tol: float = 1e-9, max_iter: int = 400) -> float:
    """Bisection IRR. Raises rather than returning a plausible wrong root."""
    if not cash_flows or all(cf >= 0 for cf in cash_flows) or all(cf <= 0 for cf in cash_flows):
        raise IRRError(
            "IRR needs at least one sign change in the cash flows. All-positive or "
            "all-negative flows have no internal rate of return.")
    sign_changes = sum(1 for a, b in pairwise(cash_flows) if (a < 0) != (b < 0))
    f_lo, f_hi = npv(lo, cash_flows), npv(hi, cash_flows)
    if f_lo * f_hi > 0:
        raise IRRError(
            f"No IRR bracketed in [{lo:.2%}, {hi:.0%}]. NPV is {f_lo:,.1f} at the low "
            f"end and {f_hi:,.1f} at the high end -- same sign, so no root in range.")
    for _ in range(max_iter):
        mid = (lo + hi) / 2
        f_mid = npv(mid, cash_flows)
        if abs(f_mid) < tol or (hi - lo) < tol:
            if sign_changes > 1:
                # Descartes: multiple sign changes permit multiple real roots.
                pass
            return mid
        if f_lo * f_mid < 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    raise IRRError(f"IRR did not converge in {max_iter} iterations.")


@dataclass(frozen=True)
class ReturnsResult:
    cash_flows: list[float]
    irr: float | None
    moic: float
    entry_equity: float
    exit_equity: float
    exit_multiple: float
    exit_year: int
    hurdle: float | None
    clears_hurdle: bool | None
    warnings: tuple[str, ...]

    def format(self) -> str:
        lines = [("ACQUISITION RETURNS (notional exit -- a strategic buyer does not "
                  "exit; this exists to compare against the buyer's cost of capital)"),
                 "-" * 76,
                 f"  Entry equity outlay          ${self.entry_equity:>12,.0f}mm",
                 (f"  Exit equity value (year {self.exit_year})   "
                  f"${self.exit_equity:>12,.0f}mm at {self.exit_multiple:.1f}x"),
                 f"  MOIC                          {self.moic:>12.2f}x"]
        lines.append(f"  IRR                           {self.irr:>12.2%}"
                     if self.irr is not None else "  IRR                           not computable")
        if self.hurdle is not None and self.irr is not None:
            state = "CLEARS" if self.clears_hurdle else "FAILS"
            lines.append(f"  vs. hurdle {self.hurdle:.2%}: {state}"
                         + ("" if self.clears_hurdle else
                            " -- returns below the cost of capital destroy value "
                            "however the EPS math lands"))
        for w in self.warnings:
            lines.append(f"  ! {w}")
        return "\n".join(lines)


def run(entry_equity_outlay: Input, free_cash_flows: list[float],
        exit_ebitda: Input, exit_multiple: Input, exit_net_debt: Input,
        hurdle_rate: Input | None = None,
        entry_multiple: float | None = None) -> ReturnsResult:
    """Build the return profile.

    `free_cash_flows` is the target-plus-synergies unlevered free cash flow by forward
    year, index 0 = year 1. `entry_equity_outlay` is the cash actually put up. Exit
    equity is exit EBITDA x exit multiple less exit net debt.
    """
    entry = entry_equity_outlay.required()
    mult = exit_multiple.required()
    exit_year = len(free_cash_flows)
    exit_equity = exit_ebitda.required() * mult - exit_net_debt.required()

    flows = [-entry] + list(free_cash_flows)
    flows[-1] += exit_equity

    warnings: list[str] = []
    if entry_multiple is not None:
        if mult > entry_multiple * 1.001:
            warnings.append(
                f"Exit multiple {mult:.1f}x exceeds entry {entry_multiple:.1f}x. Part "
                f"of this return is multiple expansion, which is an assumption about "
                f"the market, not about the business. Re-run at exit = entry to see "
                f"the operating return on its own.")
        elif abs(mult - entry_multiple) < 1e-9:
            warnings.append(
                "Exit multiple set equal to entry -- the conservative convention. The "
                "return shown is operating performance and deleveraging only, with no "
                "credit for re-rating.")

    try:
        computed = irr(flows)
    except IRRError as e:
        computed = None
        warnings.append(f"IRR not computed: {e}")

    hurdle_val = hurdle_rate.required() if hurdle_rate is not None and not hurdle_rate.is_missing else None
    clears = None if (hurdle_val is None or computed is None) else computed >= hurdle_val

    total_in = sum(cf for cf in flows[1:] if cf > 0)
    moic = total_in / entry if entry else float("inf")

    if moic < 1.0:
        warnings.append(
            "MOIC below 1.0x: the modelled cash returned is less than the cash put in "
            "even before discounting. Check the exit assumptions before reading the IRR.")

    return ReturnsResult(
        cash_flows=flows, irr=computed, moic=moic, entry_equity=entry,
        exit_equity=exit_equity, exit_multiple=mult, exit_year=exit_year,
        hurdle=hurdle_val, clears_hurdle=clears, warnings=tuple(warnings),
    )


def register(reg: AssumptionRegister, *inputs: Input | None) -> None:
    for i in inputs:
        if i is not None:
            reg.record(i)
