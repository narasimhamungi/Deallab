"""
DealLab: an M&A transaction model that answers whether an acquisition creates value for
the buyer -- and reports the accounting answer and the economic answer separately,
because they are different questions.

Built on ValuationLab (which is built on Trellis). The target's standalone valuation
arrives carrying ValuationLab's own judgement about whether its methods were fit to
produce it; if ValuationLab disqualified every method, DealLab declines to state a
premium rather than quietly using a number already flagged as unreliable.

Modules, in pipeline order:

    provenance.py          Demonstrated / Sourced / Assumed, plus the assumption register
    terms.py               consideration structure, including contingent (CVR) payouts
    calendarize.py         fiscal-year alignment and stub periods for mismatched FYEs
    financing.py           debt tranches, cash drawdown, and foregone interest income
    sources_uses.py        sources & uses with an enforced balance check
    purchase_accounting.py ASC 805 allocation, goodwill, step-up charges, DTL
    synergies.py           phased, costed, discounted; revenue synergies isolated
    proforma.py            the combination, presented as a net income bridge
    accretion.py           GAAP and adjusted separately, plus breakeven synergies
    returns.py             IRR/MOIC against the buyer's cost of capital
    verdict.py             the two lenses, structurally non-mergeable
    guidance.py            the model checked against what the buyer actually disclosed
    bridge.py              the seam to ValuationLab and Trellis
    engine.py              end-to-end orchestration
"""

__version__ = "0.1.0"
