"""
Synergies: phased, costed, discounted, and capable of being negative.

Three disciplines are enforced here, each of which a standard merger template violates.

**Run-rate is not year-one.** Announced synergies are almost always quoted as a run-rate
achieved in year three or four. Dropping the full run-rate into year one overstates
early accretion by the entire phase-in gap, which is the difference between a deal that
looks accretive from day one and one that is honestly dilutive for two years. Phase-in
is therefore mandatory, expressed as an explicit per-year realisation schedule rather
than a smooth default.

**Synergies cost money to get.** Restructuring, integration, systems, severance,
retention. Cost to achieve is typically 1x to 2x the annual run-rate, front-loaded. It
is excluded from adjusted EPS by every buyer that reports it, which is precisely why it
belongs in the economic lens even when it is absent from the accounting one.

**Revenue synergies are not cost synergies.** Cost synergies are reasonably estimable
and reasonably attainable. Revenue synergies -- cross-sell, channel leverage, pricing --
are neither, and academic and practitioner evidence consistently finds them the ones
that fail to materialise. They are tracked as a separate category so the value case can
be re-run without them, which is the sensitivity that matters most.

A fourth point, specific to the J&J/Abiomed structure and the reason `DIS_SYNERGY`
exists as a category: J&J disclosed that Abiomed would operate as a **standalone
business** within MedTech. A standalone operating model is a deliberate choice to give
up most cost synergy in order to protect the acquired franchise's momentum. A model that
assumes generic 5%-of-target-opex cost synergies for a deal the acquirer explicitly
structured to avoid integration is not being conservative or aggressive -- it is
contradicting a disclosed fact.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .provenance import AssumptionRegister, Input


class SynergyType(Enum):
    COST = "Cost"
    REVENUE = "Revenue"
    TAX = "Tax"
    DIS_SYNERGY = "Dis-synergy"  # negative: customer loss, attrition, disruption


@dataclass(frozen=True)
class SynergyItem:
    """One synergy stream.

    `run_rate` is the annual pre-tax amount at full realisation. `phase_in` is the
    fraction realised in each forward year, index 0 = year 1. It need not reach 1.0 and
    need not be monotonic -- a stream that ramps and then decays is a legitimate shape.
    `margin` applies only to revenue synergies: incremental revenue is not incremental
    profit, and a model that treats a revenue synergy as a pre-tax profit synergy
    overstates it by the whole cost base.
    """
    label: str
    type: SynergyType
    run_rate: Input                 # USD millions per year, pre-tax, at full run-rate
    phase_in: tuple[float, ...]     # realisation fraction by forward year
    margin: Input | None = None     # contribution margin on revenue synergies
    source: str = ""

    def __post_init__(self):
        if self.type is SynergyType.REVENUE and self.margin is None:
            raise ValueError(
                f"Revenue synergy '{self.label}' has no contribution margin. Booking "
                f"incremental revenue as if it were incremental profit is the single "
                f"most common way synergy cases are inflated.")
        if any(p < 0 for p in self.phase_in):
            raise ValueError(
                f"'{self.label}' has a negative phase-in fraction. To model a negative "
                f"synergy use SynergyType.DIS_SYNERGY with a positive run_rate -- the "
                f"sign belongs to the category, not to the schedule.")

    def pretax_benefit(self, year_index: int) -> float:
        """Signed pre-tax P&L effect in a forward year. Dis-synergies come back negative."""
        i = year_index - 1
        if i < 0:
            return 0.0
        fraction = self.phase_in[i] if i < len(self.phase_in) else self.phase_in[-1]
        amount = self.run_rate.required() * fraction
        if self.type is SynergyType.REVENUE:
            amount *= self.margin.required()
        return -amount if self.type is SynergyType.DIS_SYNERGY else amount


@dataclass(frozen=True)
class CostToAchieve:
    """One-time integration/restructuring spend, by forward year."""
    schedule: tuple[float, ...]  # USD millions, index 0 = year 1
    citation: str = ""

    def amount(self, year_index: int) -> float:
        i = year_index - 1
        return self.schedule[i] if 0 <= i < len(self.schedule) else 0.0

    @property
    def total(self) -> float:
        return sum(self.schedule)


@dataclass(frozen=True)
class SynergyYear:
    year_index: int
    cost: float
    revenue: float
    tax: float
    dis_synergy: float
    gross_pretax: float
    cost_to_achieve: float
    net_pretax: float


@dataclass(frozen=True)
class SynergyCase:
    items: tuple[SynergyItem, ...]
    cost_to_achieve: CostToAchieve | None = None

    def year(self, year_index: int) -> SynergyYear:
        by_type = {t: 0.0 for t in SynergyType}
        for item in self.items:
            by_type[item.type] += item.pretax_benefit(year_index)
        gross = sum(by_type.values())
        cta = self.cost_to_achieve.amount(year_index) if self.cost_to_achieve else 0.0
        return SynergyYear(
            year_index=year_index,
            cost=by_type[SynergyType.COST], revenue=by_type[SynergyType.REVENUE],
            tax=by_type[SynergyType.TAX], dis_synergy=by_type[SynergyType.DIS_SYNERGY],
            gross_pretax=gross, cost_to_achieve=cta, net_pretax=gross - cta,
        )

    def run_rate_total(self) -> float:
        """Full-realisation annual pre-tax benefit, all categories netted."""
        total = 0.0
        for item in self.items:
            amount = item.run_rate.required()
            if item.type is SynergyType.REVENUE:
                amount *= item.margin.required()
            total += -amount if item.type is SynergyType.DIS_SYNERGY else amount
        return total

    def npv(self, discount_rate: Input, tax_rate: Input, years: int = 10,
            terminal_growth: Input | None = None) -> SynergyNPV:
        """After-tax present value of the synergy case, net of cost to achieve.

        Discounting synergies at the buyer's WACC is the convention and it is arguably
        too generous: synergy cash flows are riskier than the buyer's existing business,
        which is what makes them worth paying a premium to acquire in the first place.
        Using a premium over WACC is more defensible. Whatever rate is used, it is an
        explicit input here rather than silently inherited.
        """
        r = discount_rate.required()
        t = tax_rate.required()
        pv_benefit = 0.0
        pv_cta = 0.0
        for y in range(1, years + 1):
            sy = self.year(y)
            df = (1 + r) ** -y
            pv_benefit += sy.gross_pretax * (1 - t) * df
            pv_cta += sy.cost_to_achieve * (1 - t) * df

        pv_terminal = 0.0
        if terminal_growth is not None and not terminal_growth.is_missing:
            g = terminal_growth.required()
            if g >= r:
                raise ValueError(
                    f"Synergy terminal growth {g:.2%} >= discount rate {r:.2%}: the "
                    f"perpetuity does not converge. A synergy stream growing forever "
                    f"at or above the cost of capital is infinite value, which is not "
                    f"a modelling result, it is a modelling error.")
            final = self.year(years).gross_pretax * (1 - t)
            pv_terminal = (final * (1 + g) / (r - g)) * (1 + r) ** -years

        return SynergyNPV(
            pv_benefit=pv_benefit, pv_cost_to_achieve=pv_cta, pv_terminal=pv_terminal,
            net_npv=pv_benefit - pv_cta + pv_terminal,
            horizon_years=years, discount_rate=r,
            includes_terminal=terminal_growth is not None and not terminal_growth.is_missing,
        )

    def npv_excluding_revenue_synergies(self, discount_rate: Input, tax_rate: Input,
                                        years: int = 10,
                                        terminal_growth: Input | None = None) -> SynergyNPV:
        """The sensitivity that matters: value if the revenue synergies never arrive."""
        kept = tuple(i for i in self.items if i.type is not SynergyType.REVENUE)
        return SynergyCase(kept, self.cost_to_achieve).npv(
            discount_rate, tax_rate, years, terminal_growth)

    def register(self, reg: AssumptionRegister) -> None:
        for i in self.items:
            reg.record(i.run_rate)
            if i.margin is not None:
                reg.record(i.margin)


@dataclass(frozen=True)
class SynergyNPV:
    pv_benefit: float
    pv_cost_to_achieve: float
    pv_terminal: float
    net_npv: float
    horizon_years: int
    discount_rate: float
    includes_terminal: bool

    def format(self) -> str:
        lines = [
            (f"PV of synergy benefit ({self.horizon_years}yr, after tax) "
             f"${self.pv_benefit:>12,.0f}mm"),
            f"PV of terminal synergy value              ${self.pv_terminal:>12,.0f}mm",
            f"Less PV of cost to achieve                ${-self.pv_cost_to_achieve:>12,.0f}mm",
            f"NET SYNERGY NPV                           ${self.net_npv:>12,.0f}mm",
            f"  discounted at {self.discount_rate:.2%}"
            + ("" if self.includes_terminal else "; no terminal value -- synergies "
               "assumed to stop at the horizon, which understates a genuinely "
               "permanent cost saving and is the conservative choice"),
        ]
        return "\n".join(lines)
