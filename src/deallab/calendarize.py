"""
Fiscal-year alignment between buyer and target.

This module exists because of a specific, real problem in the J&J/Abiomed deal: J&J
reports on a calendar year ending the Sunday nearest December 31; Abiomed reported on a
fiscal year ending March 31. Combining a target's FY2022 (April 2021 - March 2022) into
a buyer's FY2022 (January - December 2022) and calling the result "pro-forma FY2022" is
wrong by a three-quarter offset, and for a target growing revenue at ~22% a year that
offset is not cosmetic -- it misstates the contributed revenue by roughly a sixth.

Most merger-model templates do not have this module at all. They assume both companies
report on the same calendar and the analyst silently eats the error.

Two mechanisms:

1. `calendarize` -- linear-interpolate a target's fiscal-year flow figures onto the
   buyer's fiscal calendar by month-weighting adjacent fiscal years. Linear within the
   year is an approximation and is labelled as one. It is materially better than
   ignoring the offset and materially worse than using the target's actual quarterly
   filings, which is the upgrade path.
2. `stub_period` -- the partial year between close and the buyer's next fiscal year
   end, which is the only part of the target's earnings that lands in the year of
   close. Abiomed closed 22 December 2022: nine days of J&J's FY2022. That is why J&J
   was able to say the transaction "will not have a material impact on financial
   results for 2022" -- and a model that contributes a full year of Abiomed earnings to
   FY2022 will contradict a disclosed fact.

Balance-sheet (instant) items are NOT calendarized. A balance sheet is a point in time
and gets consolidated at its acquisition-date value under ASC 805; interpolating it
would be a category error. `calendarize` therefore takes flow items only, by name, and
refuses silently-wrong input rather than guessing which is which.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

# Flow (period) concepts from the Trellis schema. Anything not in this set is treated
# as instant and rejected by calendarize -- an explicit allowlist, because the failure
# mode of guessing wrong here is a plausible-looking wrong number.
FLOW_ITEMS: frozenset[str] = frozenset({
    "revenue", "cost_of_revenue", "gross_profit", "sga_expense", "rnd_expense",
    "operating_income", "interest_expense", "income_tax_expense", "net_income",
    "depreciation_amortization", "capex", "dividends_paid",
})


class CalendarizationError(ValueError):
    pass


@dataclass(frozen=True)
class FiscalCalendar:
    """A company's fiscal year convention, reduced to the month its FY ends."""
    name: str
    fy_end_month: int  # 1-12

    def __post_init__(self):
        if not 1 <= self.fy_end_month <= 12:
            raise ValueError(f"fy_end_month must be 1-12, got {self.fy_end_month}")

    def months_of_overlap(self, other: FiscalCalendar) -> int:
        """How many months of this company's FY sit inside the other's same-labelled FY.

        Example: Abiomed FYE March, J&J FYE December. Abiomed's FY2022 runs Apr-21 to
        Mar-22, of which three months (Jan-Mar 2022) fall inside J&J's calendar 2022.

        Derivation, with fiscal years labelled by the calendar year in which they end:
        this FY(n) spans absolute months [12(n-1)+m_t+1, 12n+m_t] and the other's FY(n)
        spans [12(n-1)+m_b+1, 12n+m_b]. The intersection is 12 - |m_b - m_t| months.
        """
        return 12 - abs(other.fy_end_month - self.fy_end_month)


@dataclass(frozen=True)
class CalendarizedYear:
    buyer_fiscal_year: int
    values: dict[str, float]
    method: str
    caveat: str


def calendarize(target_years: dict[int, dict[str, float]],
                target_cal: FiscalCalendar, buyer_cal: FiscalCalendar,
                buyer_fiscal_year: int,
                items: tuple[str, ...] | None = None) -> CalendarizedYear:
    """Re-express a target's fiscal-year flows onto the buyer's fiscal year.

    `target_years` is keyed by the target's own fiscal-year label -- the same shape
    Trellis's AnnualTable uses. The weighting blends the target FY that ends inside the
    buyer's year with the one that follows it.

    Returns a CalendarizedYear whose `method` states the weights actually applied, so
    the approximation is legible in the output rather than buried here.
    """
    if target_cal.fy_end_month == buyer_cal.fy_end_month:
        if buyer_fiscal_year not in target_years:
            raise CalendarizationError(
                f"Calendars already aligned but target has no FY{buyer_fiscal_year}. "
                f"Available: {sorted(target_years)}")
        return CalendarizedYear(
            buyer_fiscal_year, dict(target_years[buyer_fiscal_year]),
            method="no adjustment -- buyer and target share a fiscal year end",
            caveat="")

    requested = tuple(items) if items else tuple(
        k for k in next(iter(target_years.values())) if k in FLOW_ITEMS)
    bad = [i for i in requested if i not in FLOW_ITEMS]
    if bad:
        raise CalendarizationError(
            f"Cannot calendarize {bad}: not period-flow concepts. Balance-sheet items "
            f"are point-in-time and are consolidated at acquisition-date value under "
            f"ASC 805, not interpolated across a fiscal offset.")

    # Months of the target's FY(n) that fall inside the buyer's FY(n).
    overlap = target_cal.months_of_overlap(buyer_cal)
    w_early = overlap / 12.0          # weight on the target FY ending inside buyer's year
    w_late = 1.0 - w_early            # weight on the following target FY

    early, late = buyer_fiscal_year, buyer_fiscal_year + 1
    missing = [y for y in (early, late) if y not in target_years]
    if missing:
        raise CalendarizationError(
            f"Calendarizing buyer FY{buyer_fiscal_year} needs target FY{early} and "
            f"FY{late}; missing {missing}. Available: {sorted(target_years)}. "
            f"Extrapolating the missing year would fabricate the growth rate that "
            f"drives the whole contribution.")

    values = {
        item: target_years[early][item] * w_early + target_years[late][item] * w_late
        for item in requested
    }
    return CalendarizedYear(
        buyer_fiscal_year, values,
        method=(f"{w_early:.0%} x target FY{early} + {w_late:.0%} x target FY{late} "
                f"(target FYE month {target_cal.fy_end_month}, buyer FYE month "
                f"{buyer_cal.fy_end_month})"),
        caveat=("Linear within-year weighting. Assumes flows are spread evenly across "
                "the target's fiscal year, which is false for any seasonal business "
                "and inexact for a fast-growing one. Upgrade path: rebuild from the "
                "target's actual quarterly filings instead of interpolating annuals."),
    )


@dataclass(frozen=True)
class StubPeriod:
    close_date: str
    buyer_fy_end: str
    days: int
    fraction_of_year: float
    caveat: str


def stub_period(close_date: str, buyer_fy_end_month: int,
                buyer_fy_end_day: int = 31) -> StubPeriod:
    """The fraction of the buyer's fiscal year that the target is owned in year of close.

    This is what determines whether the deal moves the year-of-close numbers at all.
    A December close into a December fiscal year end contributes days, not quarters --
    which is exactly why J&J could state the Abiomed acquisition would not materially
    affect 2022 results despite a $16.6bn price.
    """
    close = date.fromisoformat(close_date)
    year = close.year if (close.month, close.day) <= (buyer_fy_end_month, buyer_fy_end_day) \
        else close.year + 1
    fy_end = date(year, buyer_fy_end_month, buyer_fy_end_day)
    days = (fy_end - close).days
    if days < 0:
        raise CalendarizationError(
            f"Close {close_date} computes to a negative stub against FY end {fy_end}. "
            f"Check the fiscal year end convention.")
    return StubPeriod(
        close_date=close_date, buyer_fy_end=fy_end.isoformat(), days=days,
        fraction_of_year=days / 365.0,
        caveat=("Straight-line day-count. Real contribution depends on the target's "
                "seasonality within the stub and on how much of the purchase "
                "accounting hits immediately (inventory step-up unwinds through COGS "
                "within roughly one inventory turn, not evenly over the year)."),
    )
