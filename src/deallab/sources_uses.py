"""
Sources & uses -- and the check that it balances.

Trellis's contribution to this portfolio was not that it built statements; it was that
it refused to present statements that failed structural integrity checks. Sources & uses
is the transaction-model equivalent of the balance-sheet-balances check: sources must
equal uses to the cent, and a model that presents an unbalanced one has a defect
upstream that will propagate silently into the pro-forma balance sheet.

So `build` returns a result carrying an explicit `balanced` flag and the signed gap,
and every downstream consumer is expected to look at it. Following Trellis's convention,
the check reports rather than raises: an unbalanced S&U is diagnostic information about
which input is wrong, and throwing it away by raising immediately would make it harder
to find, not easier.

One genuine subtlety, and it is the thing interviewers probe: transaction fees split in
two directions. Debt issuance costs are capitalised and amortised against the debt
(ASC 835-30); advisory, legal and other deal costs are expensed as incurred
(ASC 805-10-25-23) and never touch goodwill. Both are uses of cash at close. Only one
of them later shows up as a recurring charge. `financing.py` keeps them apart and this
module preserves the split rather than lumping them into one "fees" line.
"""

from __future__ import annotations

from dataclasses import dataclass

from .financing import FinancingPlan
from .terms import DealTerms


@dataclass(frozen=True)
class SourcesUses:
    sources: dict[str, float]
    uses: dict[str, float]
    total_sources: float
    total_uses: float
    gap: float
    balanced: bool
    note: str

    def format(self, width: int = 40) -> str:
        lines = ["SOURCES", "-" * (width + 16)]
        for k, v in self.sources.items():
            lines.append(f"  {k:<{width}} ${v:>12,.0f}mm")
        lines.append(f"  {'TOTAL SOURCES':<{width}} ${self.total_sources:>12,.0f}mm")
        lines += ["", "USES", "-" * (width + 16)]
        for k, v in self.uses.items():
            lines.append(f"  {k:<{width}} ${v:>12,.0f}mm")
        lines.append(f"  {'TOTAL USES':<{width}} ${self.total_uses:>12,.0f}mm")
        lines.append("")
        status = "BALANCES" if self.balanced else f"DOES NOT BALANCE (gap {self.gap:+,.1f}mm)"
        lines.append(f"  Check: {status}")
        if self.note:
            lines.append(f"  {self.note}")
        return "\n".join(lines)


def build(terms: DealTerms, plan: FinancingPlan,
          refinance_target_debt: bool = True,
          tolerance_mm: float = 0.5,
          fund_contingent_at_close: bool = False) -> SourcesUses:
    """Construct the sources & uses table.

    `fund_contingent_at_close` controls whether contingent consideration (a CVR) is
    shown as a use of cash at close. It defaults to FALSE, which is the accounting
    reality: a CVR is recognised as a LIABILITY at acquisition date and consumes cash
    only later, if and when its milestones are met. It is part of consideration
    transferred -- so it belongs in the goodwill calculation, and `terms.
    total_equity_purchase_price()` includes it -- but it is not money the buyer has to
    raise on day one. Showing it as a day-one use overstates the funding requirement by
    its full fair value (on J&J/Abiomed, $781mm at the weight this model carries) and
    makes the financing plan look larger, and therefore the interest drag heavier, than
    the deal actually demanded. Set True only to model a structure where the contingent
    amount is escrowed or prefunded at close.

    `refinance_target_debt` controls whether the target's existing debt is repaid at
    close (the usual assumption for a strategic acquisition of a leveraged target, and
    the one implied by paying an enterprise value) or assumed to remain outstanding and
    be consolidated. This is a real structural choice with a real EPS consequence, so it
    is a parameter rather than a hardcoded convention -- but note that if the target has
    net cash, "refinancing" it is not a use at all; the acquired cash is a source.
    """
    net_debt = terms.target_net_debt.required()

    sources: dict[str, float] = {}
    if plan.cash_on_hand_used.required() > 0:
        sources["Buyer cash on hand"] = plan.cash_on_hand_used.required()
    for t in plan.tranches:
        sources[f"New debt -- {t.label}"] = t.principal.required()
    if plan.new_equity_issued is not None and not plan.new_equity_issued.is_missing:
        sources["New equity issued"] = plan.new_equity_issued.required()
    if refinance_target_debt and net_debt < 0:
        # Target has net cash: the cash comes across at close and funds part of the price.
        sources["Target cash acquired"] = -net_debt

    uses: dict[str, float] = {
        "Upfront equity consideration": terms.upfront_equity_purchase_price(),
    }
    contingent = terms.contingent_consideration_fair_value()
    if contingent and fund_contingent_at_close:
        uses["Contingent consideration (CVR, prefunded at close)"] = contingent
    if refinance_target_debt and net_debt > 0:
        uses["Repay target debt"] = net_debt
    fees = plan.expensed_transaction_costs()
    if fees:
        uses["Advisory/legal fees (expensed)"] = fees
    issuance = plan.total_issuance_fees()
    if issuance:
        uses["Debt issuance costs (capitalised)"] = issuance

    total_sources = sum(sources.values())
    total_uses = sum(uses.values())
    gap = total_sources - total_uses
    balanced = abs(gap) <= tolerance_mm

    note = ""
    if not balanced:
        note = (f"Gap of ${gap:+,.1f}mm. A surplus means the funding plan raises more "
                f"than the deal needs; a shortfall means it raises less. Neither is a "
                f"rounding artefact at this size -- the defect is in an input "
                f"(share count, net debt, tranche sizing), not here.")
    elif contingent and not fund_contingent_at_close:
        note = (f"CVR of ${contingent:,.0f}mm (probability-weighted fair value, not "
                f"maximum payout) is deliberately EXCLUDED from uses: under ASC 805 it "
                f"is an acquisition-date liability, not cash out at close, so the buyer "
                f"does not fund it on day one. It remains part of consideration "
                f"transferred and therefore part of goodwill -- see the purchase price "
                f"allocation, where it does appear.")
    elif contingent:
        note = ("CVR shown as prefunded at close, which is NOT the default treatment. "
                "Only correct if the structure escrows the contingent amount up front.")

    return SourcesUses(sources, uses, total_sources, total_uses, gap, balanced, note)
