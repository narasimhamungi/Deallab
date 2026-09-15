"""
Purchase price allocation under ASC 805, and the earnings drag it creates.

This is the module that separates a transaction model from a spreadsheet that adds two
income statements together. The mechanics that matter, in the order they bite:

1. Consideration transferred is allocated to the target's identifiable assets and
   liabilities at fair value. The residual is goodwill.
2. Fair value usually exceeds book value. The step-up on identifiable intangibles
   (developed technology, customer relationships, tradenames) is amortised through the
   income statement over its useful life. Goodwill is not amortised -- it is tested for
   impairment. This asymmetry is the entire reason GAAP and adjusted EPS diverge in an
   acquisition, and it is the first thing a technical interviewer asks about.
3. The intangible step-up is generally not deductible for tax in a stock acquisition,
   so a deferred tax liability is recognised at the buyer's tax rate on the step-up.
   The DTL increases the amount allocated away from identifiable net assets, which
   increases goodwill. Models that skip the DTL understate goodwill by roughly a
   quarter of the step-up and are wrong in a way that is easy to spot.
4. Inventory is written up to fair value and unwinds through cost of sales as that
   inventory is sold -- typically within one turn, so it is a large, short, non-recurring
   hit, not a smooth amortisation. Modelling it as a multi-year charge is wrong;
   ignoring it makes year-one gross margin look better than it will be.

What is deliberately NOT here: bargain purchase gains, non-controlling interests,
measurement-period adjustments, and replacement share-based payment awards. Each is real
and each is out of scope; stating so is better than a module that silently handles none
of them while appearing complete.
"""

from __future__ import annotations

from dataclasses import dataclass

from .provenance import AssumptionRegister, Input


@dataclass(frozen=True)
class IntangibleClass:
    """One identifiable intangible recognised in the allocation.

    Pass `useful_life_years=None` for an INDEFINITE-LIVED asset. In-process research and
    development acquired in a business combination is the standard case: under ASC
    350-30, IPR&D is capitalised as indefinite-lived and NOT amortised until the
    associated project is completed (at which point it is reclassified and amortised) or
    abandoned (written off). Until then it is tested for impairment, like goodwill.

    This matters more than it looks. An earlier version of this class could only
    represent finite-life assets, which forced IPR&D to be either excluded from the
    allocation entirely -- dumping it into goodwill and overstating goodwill by its full
    value -- or given an invented finite life, which would create amortisation expense
    that does not exist and understate earnings every year. Neither is acceptable when
    the buyer discloses the split: on J&J/Abiomed, IPR&D is $1.1bn of a $17.9bn
    consideration, so mis-slotting it moves goodwill by 6% of the deal.
    """
    label: str
    fair_value: Input                     # USD millions
    useful_life_years: Input | None       # None = indefinite-lived (IPR&D); not amortised
    tax_deductible: bool = False  # True only in an asset deal / 338(h)(10) election

    @property
    def indefinite_lived(self) -> bool:
        return self.useful_life_years is None or self.useful_life_years.is_missing

    def annual_amortisation(self) -> float:
        if self.indefinite_lived:
            return 0.0
        return self.fair_value.required() / self.useful_life_years.required()

    def amortisation(self, year_index: int) -> float:
        """Straight-line, ceasing after useful life. Zero forever if indefinite-lived.

        Straight-line is the common convention and is what buyers disclose. Accelerated
        or pattern-of-benefit amortisation is permitted and is more defensible for
        customer relationships with attrition, but it is not what gets disclosed, so
        straight-line keeps the model comparable to the buyer's own numbers.

        Deliberately NOT modelled for indefinite-lived assets: the reclassification to
        finite-life on project completion, and the impairment write-off on abandonment.
        Both are real and both would create earnings volatility this model does not
        attempt to predict -- stated rather than silently ignored.
        """
        if self.indefinite_lived:
            return 0.0
        return self.annual_amortisation() if year_index <= self.useful_life_years.required() else 0.0


@dataclass(frozen=True)
class AllocationResult:
    consideration_transferred: float
    target_book_equity: float
    identifiable_intangibles: float
    inventory_step_up: float
    ppe_step_up: float
    deferred_tax_liability: float
    goodwill: float
    goodwill_pct_of_consideration: float
    notes: tuple[str, ...]

    def format(self) -> str:
        rows = [
            ("Consideration transferred", self.consideration_transferred),
            ("Less: target book equity", -self.target_book_equity),
            ("Less: identifiable intangibles at FV", -self.identifiable_intangibles),
            ("Less: inventory step-up", -self.inventory_step_up),
            ("Less: PP&E step-up", -self.ppe_step_up),
            ("Plus: deferred tax liability on step-up", self.deferred_tax_liability),
            ("= Goodwill", self.goodwill),
        ]
        lines = ["PURCHASE PRICE ALLOCATION", "-" * 60]
        for label, v in rows:
            if abs(v) < 0.5 and not label.startswith("="):
                continue  # a zero line item is noise, not information
            lines.append(f"  {label:<42} ${v:>12,.0f}mm")
        lines.append(f"  {'Goodwill as % of consideration':<42} "
                     f"{self.goodwill_pct_of_consideration:>12.1%}")
        for n in self.notes:
            lines.append(f"  ! {n}")
        return "\n".join(lines)


def allocate(consideration_transferred: float,
             target_book_equity: Input,
             intangibles: tuple[IntangibleClass, ...],
             buyer_tax_rate: Input,
             inventory_step_up: Input | None = None,
             ppe_step_up: Input | None = None,
             step_up_tax_deductible: bool = False,
             sourced_deferred_tax_liability: Input | None = None) -> AllocationResult:
    """Allocate consideration and solve for goodwill.

    `step_up_tax_deductible` is the stock-vs-asset-deal switch. In a public stock
    acquisition -- which is what a tender offer is -- the step-up is generally NOT
    deductible, a DTL arises, and goodwill increases. The default here is the stock-deal
    treatment because that is what public-company M&A almost always is; flipping it
    should be a deliberate act with a reason.

    `sourced_deferred_tax_liability` overrides the computed DTL with a disclosed one.
    Where the buyer's own filings state the DTL arising from the acquisition, that
    figure beats anything this function derives: the computed version applies a single
    statutory rate to the whole step-up, while the real DTL reflects jurisdictional mix,
    the deductible/non-deductible split across intangible classes, and any valuation
    allowance. Computing a number when a disclosed one exists, and then using the
    computed one, is the specific failure this parameter prevents.
    """
    intangible_fv = sum(i.fair_value.required() for i in intangibles)
    inv = inventory_step_up.required() if inventory_step_up and not inventory_step_up.is_missing else 0.0
    ppe = ppe_step_up.required() if ppe_step_up and not ppe_step_up.is_missing else 0.0
    total_step_up = intangible_fv + inv + ppe

    notes: list[str] = []
    if sourced_deferred_tax_liability is not None and not sourced_deferred_tax_liability.is_missing:
        dtl = sourced_deferred_tax_liability.required()
        computed = 0.0 if step_up_tax_deductible else total_step_up * buyer_tax_rate.required()
        notes.append(
            f"DTL of ${dtl:,.0f}mm taken from disclosure, not computed. This model's "
            f"own statutory-rate calculation would have given ${computed:,.0f}mm, a "
            f"${dtl - computed:+,.0f}mm difference -- which flows straight into "
            f"goodwill. The gap is the distance between a single-rate approximation and "
            f"the real jurisdictional mix; where the disclosed figure exists it wins.")
    else:
        dtl = 0.0 if step_up_tax_deductible else total_step_up * buyer_tax_rate.required()

    book = target_book_equity.required()
    goodwill = consideration_transferred - book - total_step_up + dtl

    if goodwill < 0:
        notes.append(
            "Negative goodwill. Either the allocation exceeds what was paid -- which "
            "means the fair values are too aggressive -- or this is a genuine bargain "
            "purchase, which under ASC 805 is recognised as a gain in earnings, not as "
            "negative goodwill on the balance sheet. This model does not handle bargain "
            "purchases; treat this as an input error until proven otherwise.")
    if consideration_transferred and goodwill / consideration_transferred > 0.75:
        notes.append(
            f"Goodwill is {goodwill / consideration_transferred:.0%} of consideration. "
            f"That is high: it says most of what was bought could not be identified as "
            f"a separable asset. Defensible for a growth platform acquisition, but it "
            f"concentrates the entire value case in synergies and future growth, and "
            f"it is the balance that gets impaired first if either disappoints.")
    if not intangibles:
        notes.append(
            "No identifiable intangibles supplied -- every dollar of premium has fallen "
            "into goodwill. For a technology or device target that is almost certainly "
            "wrong; it also removes all amortisation, which artificially eliminates the "
            "GAAP-vs-adjusted EPS gap this model exists to show.")

    indefinite = [i for i in intangibles if i.indefinite_lived]
    if indefinite:
        total_indef = sum(i.fair_value.required() for i in indefinite)
        notes.append(
            f"${total_indef:,.0f}mm of indefinite-lived intangibles "
            f"({', '.join(i.label for i in indefinite)}) is recognised as an "
            f"identifiable asset and reduces goodwill, but carries NO amortisation -- "
            f"ASC 350-30. It creates no GAAP-vs-adjusted gap and no annual earnings "
            f"drag, unlike the amortisable classes. It does sit inside the step-up on "
            f"which the deferred tax liability is computed.")

    return AllocationResult(
        consideration_transferred=consideration_transferred,
        target_book_equity=book,
        identifiable_intangibles=intangible_fv,
        inventory_step_up=inv,
        ppe_step_up=ppe,
        deferred_tax_liability=dtl,
        goodwill=goodwill,
        goodwill_pct_of_consideration=(goodwill / consideration_transferred
                                       if consideration_transferred else 0.0),
        notes=tuple(notes),
    )


@dataclass(frozen=True)
class StepUpCharges:
    """Pre-tax income-statement charges created by the allocation, by forward year."""
    intangible_amortisation: float
    inventory_step_up_unwind: float
    incremental_depreciation: float

    @property
    def total(self) -> float:
        return (self.intangible_amortisation + self.inventory_step_up_unwind
                + self.incremental_depreciation)

    @property
    def recurring(self) -> float:
        """The part that recurs. Inventory unwind does not."""
        return self.intangible_amortisation + self.incremental_depreciation


def step_up_charges(year_index: int, intangibles: tuple[IntangibleClass, ...],
                    allocation: AllocationResult,
                    inventory_turns_per_year: Input | None = None,
                    ppe_remaining_life_years: Input | None = None) -> StepUpCharges:
    """Charges in a given forward year (1 = first full year after close).

    Inventory step-up unwinds over 1/turns of a year, so at 2 turns it is fully
    expensed inside year one. Anything above one turn means the whole write-up hits
    year one -- which is why year-one adjusted EPS guidance from buyers almost always
    excludes it.
    """
    amort = sum(i.amortisation(year_index) for i in intangibles)

    inv_unwind = 0.0
    if allocation.inventory_step_up and year_index == 1:
        inv_unwind = allocation.inventory_step_up
    elif allocation.inventory_step_up and inventory_turns_per_year is not None:
        turns = inventory_turns_per_year.required()
        years_to_unwind = max(1.0 / turns, 0.0) if turns else 1.0
        inv_unwind = allocation.inventory_step_up if year_index <= years_to_unwind else 0.0

    dep = 0.0
    if allocation.ppe_step_up and ppe_remaining_life_years is not None \
            and not ppe_remaining_life_years.is_missing:
        life = ppe_remaining_life_years.required()
        dep = allocation.ppe_step_up / life if year_index <= life else 0.0

    return StepUpCharges(amort, inv_unwind, dep)


def register(reg: AssumptionRegister, intangibles: tuple[IntangibleClass, ...],
             *inputs: Input | None) -> None:
    for i in intangibles:
        reg.record(i.fair_value)
        if i.useful_life_years is not None:  # None = indefinite-lived, no life to record
            reg.record(i.useful_life_years)
    for x in inputs:
        if x is not None:
            reg.record(x)
