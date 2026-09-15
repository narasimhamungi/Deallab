import pytest
from fixtures import CITE, plan

from deallab import accretion
from deallab.proforma import StandaloneYear, combine
from deallab.provenance import sourced
from deallab.purchase_accounting import StepUpCharges
from deallab.synergies import SynergyYear

TAX = sourced("tax", 0.20, CITE)
SHARES = sourced("shares", 1_000.0, CITE)


def _year(syn_pretax=0.0, cta=0.0, amort=0.0, inv=0.0, ownership=1.0,
          buyer_ni=5_000.0, target_ni=150.0, fees=0.0, p=None):
    return combine(
        buyer=StandaloneYear(1, 40_000.0, 8_000.0, buyer_ni),
        target=StandaloneYear(1, 1_000.0, 200.0, target_ni),
        synergy=SynergyYear(1, syn_pretax, 0.0, 0.0, 0.0, syn_pretax, cta,
                            syn_pretax - cta),
        charges=StepUpCharges(amort, inv, 0.0),
        plan=p or plan(cash=0.0, debt=0.0),
        buyer_tax_rate=TAX, target_tax_rate=TAX, buyer_shares=SHARES,
        ownership_fraction=ownership,
        expensed_transaction_costs_this_year=fees,
    )


def test_bridge_starts_at_buyer_standalone_and_sums_to_pro_forma():
    pf = _year(syn_pretax=100.0, amort=400.0)
    assert pf.gaap_net_income == pytest.approx(
        pf.buyer_net_income + sum(s.amount for s in pf.steps))


def test_amortisation_is_excluded_from_adjusted_but_not_from_gaap():
    pf = _year(amort=400.0)
    assert pf.adjusted_net_income - pf.gaap_net_income == pytest.approx(400.0 * 0.8)


def test_financing_cost_stays_inside_adjusted_earnings():
    """J&J guided year-one adjusted EPS 'considering the impact of financing'.
    Excluding interest from adjusted would make the model uncheckable."""
    pf = _year(p=plan(cash=1_000.0, debt=4_000.0))
    labels = {s.label for s in pf.steps if s.in_adjusted}
    assert "Interest on acquisition debt (after tax)" in labels
    assert "Foregone interest income on cash used (after tax)" in labels


def test_foregone_interest_income_actually_reduces_earnings():
    with_cash = _year(p=plan(cash=1_000.0, debt=0.0)).adjusted_net_income
    without = _year(p=plan(cash=0.0, debt=0.0)).adjusted_net_income
    assert without - with_cash == pytest.approx(1_000.0 * 0.04 * 0.8)


def test_transaction_costs_hit_gaap_only():
    pf = _year(fees=50.0)
    assert pf.gaap_net_income < pf.adjusted_net_income
    assert all(s.in_adjusted is False for s in pf.steps
               if "Transaction costs" in s.label)


def test_stub_year_scales_the_target_contribution():
    full = _year(ownership=1.0)
    stub = _year(ownership=0.25)
    contrib = {s.label: s.amount for s in stub.steps}["Target net income contributed"]
    assert contrib == pytest.approx(150.0 * 0.25)
    assert stub.gaap_net_income < full.gaap_net_income


def test_accretion_compares_against_the_buyers_own_standalone_eps():
    pf = _year(target_ni=150.0)
    r = accretion.compute(pf, standalone_net_income=5_000.0, standalone_shares=1_000.0)
    assert r.standalone_eps == pytest.approx(5.0)
    assert r.adjusted_pct > 0
    assert r.adjusted_verdict == "accretive"


def test_gaap_and_adjusted_are_reported_separately_and_the_gap_is_the_ppa():
    pf = _year(amort=1_000.0)
    r = accretion.compute(pf, 5_000.0, 1_000.0)
    assert r.purchase_accounting_gap_eps == pytest.approx(1_000.0 * 0.8 / 1_000.0)
    assert r.gaap_pct < r.adjusted_pct


def test_attribution_splits_the_eps_move_by_driver():
    pf = _year(syn_pretax=100.0, p=plan(cash=0.0, debt=4_000.0))
    r = accretion.compute(pf, 5_000.0, 1_000.0)
    assert "Synergies realised (after tax)" in r.attribution
    assert "Interest on acquisition debt (after tax)" in r.attribution
    assert r.attribution["Interest on acquisition debt (after tax)"] < 0


def test_breakeven_synergy_is_the_amount_that_holds_eps_flat():
    pf = _year(syn_pretax=100.0, amort=0.0, p=plan(cash=0.0, debt=4_000.0))
    b = accretion.breakeven_synergies(
        pf, 5_000.0, 1_000.0, tax_rate=0.20,
        realised_pretax_synergies=100.0, target_revenue=1_000.0)
    # rebuild at exactly the breakeven synergy: EPS should land on standalone
    rebuilt = _year(syn_pretax=b.required_pretax, p=plan(cash=0.0, debt=4_000.0))
    assert rebuilt.adjusted_eps == pytest.approx(5.0, abs=1e-9)


def test_breakeven_reports_a_shortfall_when_the_price_needs_unidentified_synergies():
    pf = _year(syn_pretax=10.0, p=plan(cash=0.0, debt=4_000.0), target_ni=20.0)
    b = accretion.breakeven_synergies(pf, 5_000.0, 1_000.0, 0.20,
                                      realised_pretax_synergies=10.0,
                                      target_revenue=1_000.0)
    assert b.shortfall_pretax > 0
    assert "nobody has identified" in b.reading


def test_breakeven_names_arithmetic_accretion_when_no_synergy_is_needed():
    pf = _year(syn_pretax=0.0, target_ni=500.0)
    b = accretion.breakeven_synergies(pf, 5_000.0, 1_000.0, 0.20,
                                      realised_pretax_synergies=0.0)
    assert b.required_pretax <= 0
    assert "not the same as value creation" in b.reading


def test_repaying_target_debt_eliminates_the_targets_own_interest():
    """Leaving the target's pre-deal interest in while also charging acquisition
    interest double-counts the cost of the same debt."""
    from deallab.proforma import StandaloneYear, combine
    from deallab.purchase_accounting import StepUpCharges
    from deallab.synergies import SynergyYear

    def build(eliminate):
        return combine(
            buyer=StandaloneYear(1, 40_000.0, 8_000.0, 5_000.0),
            target=StandaloneYear(1, 1_000.0, 200.0, 150.0, interest_expense=30.0),
            synergy=SynergyYear(1, 0, 0, 0, 0, 0, 0, 0),
            charges=StepUpCharges(0.0, 0.0, 0.0), plan=plan(cash=0.0, debt=0.0),
            buyer_tax_rate=TAX, target_tax_rate=sourced("t_tax", 0.25, CITE),
            buyer_shares=SHARES, eliminate_target_interest=eliminate)

    on, off = build(True), build(False)
    assert on.adjusted_net_income - off.adjusted_net_income == pytest.approx(30.0 * 0.75)
    assert any("target's own rate" in s.note for s in on.steps)


def test_target_interest_addback_is_absent_when_debt_is_not_refinanced():
    from deallab.proforma import StandaloneYear, combine
    from deallab.purchase_accounting import StepUpCharges
    from deallab.synergies import SynergyYear
    pf = combine(
        buyer=StandaloneYear(1, 40_000.0, 8_000.0, 5_000.0),
        target=StandaloneYear(1, 1_000.0, 200.0, 150.0, interest_expense=30.0),
        synergy=SynergyYear(1, 0, 0, 0, 0, 0, 0, 0),
        charges=StepUpCharges(0.0, 0.0, 0.0), plan=plan(cash=0.0, debt=0.0),
        buyer_tax_rate=TAX, target_tax_rate=TAX, buyer_shares=SHARES,
        eliminate_target_interest=False)
    assert not any("eliminated on refinancing" in s.label for s in pf.steps)
